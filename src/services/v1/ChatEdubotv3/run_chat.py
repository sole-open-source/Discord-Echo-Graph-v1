from sqlalchemy.orm import Session
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, ToolCall
from langgraph.graph.state import CompiledStateGraph

from typing import List, TypedDict, Any, Union, Optional, Dict

from src import settings
from src import chatedubot_models as models
from .set_langchain_messages import Ai_Message, Tool_Message, set_json_to_langchain_format, set_langchain_format_to_json

from src.logging_config import get_logger
logger = get_logger(module_name="run_chat", DIR="Agent")


def _log(session: Session, chat_id: int, msg: str) -> None:
    logger.info(msg)
    session.add(models.EduChatLogs(chat_id=chat_id, log=msg))





def set_langchain_format(message_history_records : List[models.ChatMessages], system_message : str) -> List[BaseMessage]:
    role_map = {
        models.MessageRole.HUMAN: "Human",
        models.MessageRole.AI: "Ai",
        models.MessageRole.TOOL: "Tool",
    }
    records = [{"role": "System", "content": system_message}]
    for msg in message_history_records:
        records.append({**msg.message, "role": role_map[msg.role]})
    return set_json_to_langchain_format(records)



def format_langchain_messages(session : Session, messages : List[BaseMessage], user_id : int, chat_id : int) -> List[Union[Ai_Message, Tool_Message]]:
    agent_messages : List[BaseMessage] = []
    N = len(messages) - 1
    for i in range(N):
        message = messages[N - i]
        if isinstance(message, HumanMessage):
            break
        agent_messages.append(message)
    agent_messages = list(reversed(agent_messages))

    # for msg in agent_messages:
    #     logger.info(f"{msg.pretty_repr()}")

    role_to_model = {"Ai": models.MessageRole.AI, "Tool": models.MessageRole.TOOL}
    response = []
    for data in set_langchain_format_to_json(agent_messages):
        role_str = data.pop("role")
        messages_record = models.ChatMessages(
            user_id=user_id,
            chat_id=chat_id,
            role=role_to_model[role_str],
            message=data
        )
        session.add(messages_record)
        data["type"] = role_str
        response.append(data)

    session.commit()
    return response







def run_chat(
        session : Session, 
        user_id : int, 
        chat_id : int, 
        human_message : str, 
        chat_agent : CompiledStateGraph, 
        edubot_system_message : str, 
        subagents_system_message : Dict[str, str] # Diccionario con key nombre del estado que aparece en Edubot/graph value system message
):
    
    _log(session, chat_id, "guardando human_message en la tabla de chat principal")
    chat_message_record = models.ChatMessages(
        chat_id=chat_id,
        user_id=user_id,
        role=models.MessageRole.HUMAN,
        message={"content":human_message}
    )
    

    session.add(chat_message_record)
    session.commit()
    current_message_id = chat_message_record.id
    _log(session, chat_id, f"human message guardado, message id: {current_message_id}")

    message_history_records = session.query(models.ChatMessages).filter_by(
        chat_id=chat_id,
        user_id=user_id
    ).order_by(models.ChatMessages.id).all()
    _log(session, chat_id, "Historial de mensajes conseguido")


    records_educhat_state = session.query(models.EduBotStates).filter(
        models.EduBotStates.state_name.in_(list(subagents_system_message.keys()))
    ).all()   # Aqui espero que hayan n registros correspondientes a la cantidad de subagentes
            
    
    # Como no sabemos si el agente invoko al subagente siempre inicialisamos el historial con el sytem prompt
    current_state = [
        (
            name, 
            set_json_to_langchain_format([{"role": "System", "content": subagents_system_message[name]}])
        ) 
        for name in subagents_system_message
    ]

    current_state = dict(current_state)

    # En caso de que el agente si haya invocado al subagente, actualizamos el historial
    for record in records_educhat_state:
        name = record.state_name
        json = record.state
        current_state[name] = set_json_to_langchain_format(json)
    

    messages = set_langchain_format(message_history_records=message_history_records, system_message=edubot_system_message)
    _log(session, chat_id, "Historial de mensajes en formato de langchain conseguido")

    current_state["messages"] = messages


    # Ahora invocamos
    agent_response = chat_agent.invoke(current_state)


    for key in agent_response:
        if key in list(subagents_system_message.keys()):
            agent_history = agent_response[key]
            state = set_langchain_format_to_json(agent_history)
            state_record = session.query(models.EduBotStates).filter(
                models.EduBotStates.chat_id == chat_id,
                models.EduBotStates.state_name == key
            ).first()
            
            if state_record is None:
                r = models.EduBotStates(chat_id=chat_id, state=state, state_name=key)
                session.add(r)
            else:
                state_record.state = state
                session.add(state_record)




    messages = agent_response["messages"]
    chat_response = format_langchain_messages(session=session, messages=messages, user_id=user_id, chat_id=chat_id)
    _log(session, chat_id, "los mensajes de langchain se han formateado a json")

    _log(session, chat_id, "guardando en la base de datos")
    session.close()

    return chat_response








if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src import settings
    from src import chatedubot_models as models
    from langchain_groq import ChatGroq
    from pathlib import Path

    from .OriginabotdbAgent.graph import create_chat_agent
    from .Edubot.graph import create_chat_edubot
    import json
    import asyncio


    from .Edubot.prompts import EDUBOT_SYSTEM_PROMPT_1
    from .OriginabotdbAgent.prompts import DB_AGENT_SYSTEM_PROMPT_3
    from .Edubot import conf
    

    root_dir = Path(__file__).resolve().parent
    path = root_dir / "OriginabotdbAgent" / "originabotSKILL.md"
    with open(path, "r", encoding="utf-8") as f:
        description = f.read()
    
    # TODO esto es legacy no es nesario per debe ponerse pq aun es param reque
    path = root_dir / "OriginabotdbAgent" / "originabot.json"
    with open(path, "r", encoding="utf-8") as f:
        originabotdb_json = json.load(f)
    

    DB_USER = "postgres"
    DB_PASS = "postgres"
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "originabotdb"

    model = "openai/gpt-oss-120b"
    llm = ChatGroq(model=model, temperature=0.2, api_key=settings.GROQ_API_KEY)

    originabotdb_engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    educhat_engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    EduchatSession = sessionmaker(bind=educhat_engine)
    session = EduchatSession()           # sesión principal usada por run_chat
    agent_educhat_session = EduchatSession()  # sesión dedicada para UsageMetadata de los agentes

    discord_engine = create_engine(settings.DB_DISCORD_CONN_STRING)
    DiscordSession = sessionmaker(bind=discord_engine)
    discord_session = DiscordSession()

    semaphore = asyncio.Semaphore(3)

    originabotdb_subagent = create_chat_agent(llm=llm, engine=originabotdb_engine, originabotdb_json=originabotdb_json, educhat_session=agent_educhat_session)

    subagent_dict = {
        conf.ORIGINABOT_SUBAGENT_NAME : {"state_name":"originabot_agent_history", "subagent":originabotdb_subagent}
    }

    edubot = create_chat_edubot(llm=llm, subagent_dict=subagent_dict, semaphore=semaphore, session=discord_session, educhat_session=agent_educhat_session)

    system_edubot = EDUBOT_SYSTEM_PROMPT_1

    originabot_system_message = DB_AGENT_SYSTEM_PROMPT_3.format(top_n=15, description=description)


    user_id = 1
    chat_id = 1

    human_message = "Hola"
    human_message = "cuantaos registros tiene la tabla minifarm_projectprice de originabotdb ?"
    # human_message = "listo, ahora me gustaria saber quien es Camilo Rivera en Solenium y Unergy"


    subagents_system_message = {"originabot_agent_history":originabot_system_message}

    run_chat(session=session, user_id=user_id, chat_id=chat_id, human_message=human_message, chat_agent=edubot, edubot_system_message=system_edubot, subagents_system_message=subagents_system_message)


"""
python3 -m src.services.v1.ChatEdubotv3.run_chat


"""