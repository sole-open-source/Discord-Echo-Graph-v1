from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, ToolCall
from langchain_core.messages.ai import UsageMetadata

from typing import List, TypedDict, Any, Union, Optional

from src import settings
from src import chatedubot_models as model
from .agent import create_chat_agent
from .prompts import SYSTEM_PROMPT_2
import time

from src.logging_config import get_logger
logger = get_logger(module_name="run_chat", DIR="ChatLightRagv2")



def set_langchain_format(message_history_records : List[model.ChatMessages], system_message : str) -> List[BaseMessage]:
    messages = []
    messages.append(SystemMessage(content=system_message))

    for msg in message_history_records:
        if msg.role == model.MessageRole.HUMAN:
            messages.append(HumanMessage(content=msg.message['content']))
        elif msg.role == model.MessageRole.AI:
            tool_calls = msg.message['tool_calls']
            langchain_tool_calls = [
                ToolCall(
                    name=y['name'],
                    args=y['args'],
                    id=y['id'],
                    type=y['type']
                ) for y in tool_calls
            ]
            messages.append(
                AIMessage(
                    content=msg.message['content'],
                    tool_calls=langchain_tool_calls,
                    usage_metadata=msg.message["usage_metadata"]
                )
            )
        elif msg.role == model.MessageRole.TOOL:
            messages.append(
                ToolMessage(
                    content=msg.message['content'],
                    tool_call_id=msg.message['tool_call_id'],
                    name=msg.message.get('name')
                )
            )
    
    return messages




class Ai_Message(TypedDict):
    content: Union[str, List[Union[str, dict]]]
    tool_calls: List[ToolCall]
    usage_metadata: Optional[UsageMetadata]
    type: str

class Tool_Message(TypedDict):
    content: Any
    tool_call_id: str
    name: Optional[str]
    type: str


def format_langchain_messages(session : Session, messages : List[BaseMessage], user_id : int, chat_id : int) -> List[Union[Ai_Message, Tool_Message]]:
    response = []
    agent_messages : List[BaseMessage] = []

    N = len(messages)-1
    for i in range(N):
        message = messages[N-i]
        if isinstance(message, HumanMessage):
            # recorremos los mensajes hasta encontrar el primer human message
            break
        else:
            agent_messages.append(message)

    agent_messages = list(reversed(agent_messages))

    for msg in agent_messages:
        time.sleep(0.1)
        if isinstance(msg, AIMessage):
            content = msg.content
            tool_calls = [{
                'name':x["name"],
                'args':x["args"],
                'id':x["id"],
                'type':x["type"]
            } for x in (msg.tool_calls or [])] # Por si message.tool_calls es None
            usage_metadata = msg.usage_metadata
            data = {"content":content, "tool_calls":tool_calls, "usage_metadata":usage_metadata}
            messages_record = model.ChatMessages(
                user_id=user_id,
                chat_id=chat_id,
                role=model.MessageRole.AI,
                message=data
            )
            session.add(messages_record)
            session.commit()
            data['type'] = 'Ai'
            response.append(data)
        elif isinstance(msg, ToolMessage):
            content = msg.content
            tool_call_id = msg.tool_call_id
            name = msg.name
            data = {"content":content, "tool_call_id":tool_call_id, "name":name}
            messages_record = model.ChatMessages(
                user_id=user_id,
                chat_id=chat_id,
                role=model.MessageRole.TOOL,
                message=data
            )
            session.add(messages_record)
            session.commit()
            data['type'] = 'Tool'
            response.append(data)
    
    return response 
    
            


        

def run_chat(user_id : int, chat_id : int, human_message : str, llm : BaseChatModel, system_message : str = SYSTEM_PROMPT_2) -> List[Union[Ai_Message, Tool_Message]]:
    logger.info("run_chat")
    engine = create_engine(settings.DB_NAME_EDUCHAT)
    MySession = sessionmaker(bind=engine)
    session = MySession()

    message_record = model.ChatMessages(
        chat_id=chat_id,
        user_id=user_id,
        role=model.MessageRole.HUMAN,
        message={"content":human_message}
    )

    session.add(message_record)
    session.commit()


    message_history_records = session.query(model.ChatMessages).filter_by(
        chat_id=chat_id,
        user_id=user_id
    ).order_by(model.ChatMessages.create_at).all()
    logger.info("Historial de mensajes conseguido")

    messages = set_langchain_format(message_history_records=message_history_records, system_message=system_message)
    logger.info("Historial de mensajes en formato de langchain conseguido \n\n")

    for msg in messages:
        if isinstance(msg, SystemMessage):
            continue
        logger.debug(f"{msg.pretty_repr()}")
    logger.debug("\n"*2)


    agent = create_chat_agent(llm=llm)
    logger.info("invokando al agente")
    agent_response = agent.invoke({"messages":messages})
    messages = agent_response["messages"]
    logger.info("Respuestas del agente conseguidas")

    chat_response = format_langchain_messages(session=session, messages=messages, user_id=user_id, chat_id=chat_id)
    logger.info("los mensajes de langchain se han formateado a json")

    logger.info("guardando en la base de datos")
    #session.commit()
    session.close()
    
    logger.debug("\n"*10)

    return chat_response




    
if __name__=="__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from langchain_groq import ChatGroq


    from src import chat_lightrag_models as models
    from src import settings


    # engine = create_engine(settings.CHAT_DB_APP_CONN_STRING)
    # MySession = sessionmaker(bind=engine)
    # session = MySession()

    # user_record = models.User(
    #     discord_user_id=1234567890,
    #     discord_name="Thomas",
    # )
    # session.add(user_record)

    # chat_record = models.UserChat(
    #     user_id=1
    # )
    # session.add(chat_record)

    # session.commit()

    modelo = "openai/gpt-oss-120b"
    llm = ChatGroq(model=modelo, temperature=0.2, api_key=settings.GROQ_API_KEY)

    user_id = 1
    chat_id = 1

    human_message = "muchas gracias"
    #human_message = "me gustaria saber Como va el estudio de suelos en COLBOYT123P1 ?"

    response = run_chat(user_id=user_id, chat_id=chat_id, human_message=human_message, llm=llm)

    for r in response:
        print(r)
        print("\n")
    
    print("\n"*5)








"""
python3 -m src.services.v2.ChatLightRag.run_chat


"""






