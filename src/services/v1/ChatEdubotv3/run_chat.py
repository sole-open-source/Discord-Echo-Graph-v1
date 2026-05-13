from sqlalchemy.orm import Session
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, ToolCall
from langchain_core.messages.ai import UsageMetadata
from langgraph.graph.state import CompiledStateGraph

from typing import List, TypedDict, Any, Union, Optional, Dict

from src import settings
from src import chatedubot_models as models
from .set_langchain_messages import Ai_Message, Tool_Message, set_json_to_langchain_format, set_langchain_format_to_json

from src.logging_config import get_logger
logger = get_logger(module_name="run_chat", DIR="ChatLightRagv2")





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

    for msg in agent_messages:
        logger.info(f"{msg.pretty_repr()}")

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
        originabot_system_message : str
):
    
    logger.info("guardando human_message en la tabla de chat principal")
    chat_message_record = models.ChatMessages(
        chat_id=chat_id,
        user_id=user_id,
        role=models.MessageRole.HUMAN,
        message={"content":human_message}
    )
    

    session.add(chat_message_record)
    session.commit()
    logger.info("human message guardado \n\n")

    message_history_records = session.query(models.ChatMessages).filter_by(
        chat_id=chat_id,
        user_id=user_id
    ).order_by(models.ChatMessages.id).all()
    logger.info("Historial de mensajes conseguido")


    # =========================
    # =========================
    record = session.query(models.EduBotStates).filter_by(chat_id=chat_id).first() # record.state debe ser una lista de jsons
    if record is None:
        logger.info("No hay historial del subagente")
        originabot_agent_hystory = set_json_to_langchain_format([SystemMessage(content=originabot_system_message)])
    else:
        logger.info(f"recuperando memorio del subagente. Hay {len(record.state)}")
        originabot_agent_hystory = set_json_to_langchain_format(record.state)
    # =========================
    # =========================


    messages = set_langchain_format(message_history_records=message_history_records, system_message=edubot_system_message)
    logger.info("Historial de mensajes en formato de langchain conseguido \n\n")


    agent_response = chat_agent.invoke({"messages":messages, "originabot_agent_hystory":originabot_agent_hystory})
    messages = agent_response["messages"]


    # =========================
    # =========================
    originabot_agent_hystory = agent_response["originabot_agent_hystory"]
    if originabot_agent_hystory:
        state = set_langchain_format_to_json(originabot_agent_hystory)
        record = models.EduBotStates(chat_id=chat_id, state=state)
        session.add(record)
    # =========================
    # =========================


    logger.info("Respuestas del agente conseguidas")

    chat_response = format_langchain_messages(session=session, messages=messages, user_id=user_id, chat_id=chat_id)
    logger.info("los mensajes de langchain se han formateado a json")


    logger.info("guardando en la base de datos \n\n\n\n\n\n\n\n")
    session.close()

    return chat_response








if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src import settings
    from src import chatedubot_models as models

    from Edubot.prompts import EDUBOT_SYSTEM_PROMPT_1
    from OriginabotdbAgent.prompts import DB_AGENT_SYSTEM_PROMPT_3
    
    engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()
