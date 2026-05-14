from sqlalchemy.orm import Session
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage, ToolCall
from langchain_core.messages.ai import UsageMetadata
from langgraph.graph.state import CompiledStateGraph

from typing import List, TypedDict, Any, Union, Optional, Dict

from src import settings
from src import chatedubot_models as models

# from src.logging_config import get_logger
# logger = get_logger(module_name="run_chat", DIR="ChatLightRagv2")





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
        elif msg.get("role") == "Tool":
            message = ToolMessage(
                content=msg.get("content"),
                tool_call_id=msg.get("tool_call_id"),
                name = msg.get("name")
            )
            response.append(message)
        else:
            print(f"el siguiente json no se pudo clasificar: \n {msg}")
        
    return response
        
        




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






    


    




