from sqlalchemy.orm import Session
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, ToolCall
from langchain_core.messages.ai import UsageMetadata
from langgraph.graph.state import CompiledStateGraph

from typing import List, TypedDict, Any, Union, Optional, Dict

from src import settings
from src import chatedubot_models as models

from src.logging_config import get_logger
logger = get_logger(module_name="run_chat", DIR="ChatLightRagv2")



def set_langchain_format(message_history_records : List[models.ChatMessages], system_message : str) -> List[BaseMessage]:
    """
    funcion para convertir json de la base de datos de mensajes y convertirlos a clases de mensajes de langchain
    
    """
    messages = []
    messages.append(SystemMessage(content=system_message))

    for msg in message_history_records:
        if msg.role == models.MessageRole.HUMAN:
            messages.append(HumanMessage(content=msg.message['content']))
        elif msg.role == models.MessageRole.AI:
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
        elif msg.role == models.MessageRole.TOOL:
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
    role: str

class Tool_Message(TypedDict):
    content: Any
    tool_call_id: str
    name: Optional[str]
    role: str


def format_langchain_messages(session : Session, messages : List[BaseMessage], user_id : int, chat_id : int) -> List[Union[Ai_Message, Tool_Message]]:
    """
    funcion principal para convertir messages de langchain del chatbot de EduBot a json y guardarlos en la tabla de mensajes
    """
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
        if isinstance(msg, AIMessage):
            logger.info(f"{msg.pretty_repr()}")
            content = msg.content
            tool_calls = [{
                'name':x["name"],
                'args':x["args"],
                'id':x["id"],
                'type':x["type"]
            } for x in (msg.tool_calls or [])]
            usage_metadata = msg.usage_metadata
            data = {"content":content, "tool_calls":tool_calls, "usage_metadata":usage_metadata}
            messages_record = models.ChatMessages(
                user_id=user_id,
                chat_id=chat_id,
                role=models.MessageRole.AI,
                message=data
            )
            session.add(messages_record)
            data['type'] = 'Ai'
            response.append(data)
        elif isinstance(msg, ToolMessage):
            logger.info(f"{msg.pretty_repr()}")
            content = msg.content
            tool_call_id = msg.tool_call_id
            name = msg.name
            data = {"content":content, "tool_call_id":tool_call_id, "name":name}
            messages_record = models.ChatMessages(
                user_id=user_id,
                chat_id=chat_id,
                role=models.MessageRole.TOOL,
                message=data
            )
            session.add(messages_record)
            data['type'] = 'Tool'
            response.append(data)

    session.commit()
    return response




# ==============================================================================================
# ==============================================================================================

class Human_Message(TypedDict):
    content : str
    role : str


class System_Message(TypedDict):
    content : str
    role : str


def set_langchain_format_to_json(messages : List[BaseMessage]) -> List[Union[Ai_Message, Tool_Message, Human_Message, System_Message]]:
    response = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            content = msg.content
            tool_calls = [{
                'name':x["name"],
                'args':x["args"],
                'id':x["id"],
                'type':x["type"]
            } for x in (msg.tool_calls or [])]
            usage_metadata = msg.usage_metadata
            data = {"content":content, "tool_calls":tool_calls, "usage_metadata":usage_metadata}
            data["role"] = "Ai"
            response.append(data)
        elif isinstance(msg,ToolMessage):
            content = msg.content
            content = msg.content
            tool_call_id = msg.tool_call_id
            name = msg.name
            data = {"content":content, "tool_call_id":tool_call_id, "name":name}
            data["role"] = "Tool"
            response.append(data)
        elif isinstance(msg, HumanMessage):
            content = msg.content
            data = {"content":content}
            data["role"] = "Human"
            response.append(data)
        elif isinstance(msg, SystemMessage):
            content = msg.content
            data = {"content":content}
            data["role"] = "System"
            response.append(data)
    
    return response
        


def set_json_to_langchain_format(record : List[Dict[str, Any]]) -> List[BaseMessage]:
    response = []
    for msg in record:
        if msg.get("role") == "System":
            message = SystemMessage(content=msg.get("content"))
            response.append(message)
        elif msg.get("role") == "Human":
            message = HumanMessage(content=msg.get("content"))
            response.append(message)
        elif msg.get("role") == "Ai":
            langchai_tool_calls = [
                ToolCall(
                    name=y['name'],
                    args=y['args'],
                    id=y['id'],
                    type=y['type']
                ) for y in msg.get("tool_calls")
            ]
            message = AIMessage(
                content=msg.get("content"),
                tool_calls=langchai_tool_calls,
                usage_metadata=msg.get("usage_metadata")
            )
            response.append(message)
        elif msg.get("role") == "Human":
            message = ToolMessage(
                content=msg.get("content"),
                tool_call_id=msg.get("tool_call_id"),
                name = msg.get("name")
            )
            response.append(message)
    return response
        
        





# # Nota: chat_agent debe alamcenar la memoria de la conversacion en un stade llamado messages
def run_chat(
        session : Session, 
        user_id : int, 
        chat_id : int, 
        human_message : str, 
        chat_agent : CompiledStateGraph, 
        edubot_system_message : str, 
):

    logger.info("guardando human_message en la tabla de chat principal")
    chat_message_record = models.ChatMessages(
        chat_id=chat_id,
        user_id=user_id,
        role=models.MessageRole.HUMAN,
        message={"content":human_message}
    )
    logger.info("human message guardado \n\n")

    logger.info(f"{HumanMessage(content=human_message).pretty_repr()}")

    session.add(chat_message_record)
    session.commit()

    message_history_records = session.query(models.ChatMessages).filter_by(
        chat_id=chat_id,
        user_id=user_id
    ).order_by(models.ChatMessages.id).all()
    logger.info("Historial de mensajes conseguido")


    messages = set_langchain_format(message_history_records=message_history_records, system_message=edubot_system_message)
    logger.info("Historial de mensajes en formato de langchain conseguido \n\n")


    agent_response = chat_agent.invoke({"messages":messages})
    messages = agent_response["messages"]
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
    from OriginabotdbAgent.prompts import DB_AGENT_SYSTEM_PROMPT_1
    
    engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()






    


    




