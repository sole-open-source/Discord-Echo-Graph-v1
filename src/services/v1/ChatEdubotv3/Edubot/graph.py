from src.logging_config import get_logger
from .conf import SUBAGENT_NAME
from .LightRagToolKit import LightRagToolKit
from .OriginabotdbToolKit import OriginabotdbSubAgentToolKit
from .RegularSearchToolKit.RegularSearchToolKit import RetrivePartialResponsesToolKit

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import add_messages, END, START, StateGraph
from langgraph.prebuilt import ToolNode

from typing import TypedDict, List, Annotated, Literal



logger = get_logger(module_name="chat_edubot", DIR="Agent")


class SetToolResponse(TypedDict):
    tool_message_list : List[ToolMessage]
    tool_message_subagent : ToolMessage

    


def set_tool_response(tool_responses : List[ToolMessage], tool_name : str) -> SetToolResponse:
    tool_message_list = []
    tool_message_subagent = None
    N = 0
    for msg in tool_responses:
        if msg.name == tool_name:
            N += 1
            tool_message_subagent = msg
        else:
            tool_message_list.append(msg)
    logger.info(f"Se ha llamado {N} veces al subagente")
    if N < 2:
        return {"tool_message_list":tool_message_list, "tool_message_subagent":tool_message_subagent}
    logger.error(f"tool_node_wrapper: se ha llamada un subajente 2  o mas veces a la vez")
    tool_message_subagent.content = "ERROR"
    return {"tool_message_list":tool_message_list, "tool_message_subagent":tool_message_subagent}
        

    


# =========================================================================
# =========================================================================





def create_chat_edubot(llm : BaseChatModel, originabotdb_subagent : CompiledStateGraph) -> CompiledStateGraph:

    # ==========================
    # Tools
    # ==========================

    lightrag_toolkit = LightRagToolKit()
    lightrag_tools = lightrag_toolkit.get_tools()

    originabotdb_subagent_toolkit = OriginabotdbSubAgentToolKit()
    originabot_tools = originabotdb_subagent_toolkit.get_tools()

    retrive_toolkit = RetrivePartialResponsesToolKit()
    retrive_tools = retrive_toolkit.get_tools()


    tools = lightrag_tools + originabot_tools + retrive_tools
    logger.info(f"hay {len(tools)} tools")
    llm_with_tools = llm.bind_tools(tools=tools)

    # =========================
    # Estados del grafo
    # =========================

    class State(TypedDict):
        messages : Annotated[List[BaseMessage], add_messages]
        # originabot_agent_name : str | None
        originabot_agent_hystory : List[BaseMessage]

    
    tool_invoker = ToolNode(messages_key="messages")

    # ===================
    # Nodos del grafo
    # ===================

    def ReAct_node(state : State) -> State:
        # logger.info("=== ReAct_node")
        logger.info("---"*4 + " ReAct_node \n")
        messages = state["messages"]
        # originabot_agent_hystory = None
        try:
            ai_message = llm_with_tools.invoke(messages)
            logger.info(f"\n {ai_message.pretty_repr()} \n\n")
        except Exception as e:
            logger.error(f"Error en ReAct_node: \n {e}")
            raise ValueError(f"Error: \n {e}")
        finally:
            return {"messages":ai_message}
        
    
    def tool_node_wrapper(state : State) -> State:
        # logger.info("=== tool_node_wrapper")
        logger.info("---"*4 + " tool_node_wrapper\n")
        tool_responses_ditc = tool_invoker.invoke(state) # {"messages" : [ToolMessage, ToolMessage ...]}
        logger.info("tools invocadas")
        
        tool_response : List[ToolMessage] = tool_responses_ditc["messages"]
        logger.info("set_tool_response")
        set_tool_dict = set_tool_response(tool_responses=tool_response, tool_name=SUBAGENT_NAME)
        if set_tool_dict.get("tool_message_subagent") is None:
            for msg in tool_response:
                logger.info(f"{msg.pretty_repr()}")
            return tool_responses_ditc
        
        tool_message_subagent = set_tool_dict.get("tool_message_subagent")
        tool_message_list = set_tool_dict.get("tool_message_list")
        if tool_message_subagent.content == "ERROR":
            tool_message_subagent.content = "Error: No puedes llamar al subagente mas de 1 vez al mismo tiempo. Invoca al subagente con un sola tarea a la vez"
            result = tool_message_list + [tool_message_subagent]
            for msg in result:
                logger.info(f"{msg.pretty_repr()}")
            return {"messages":result}
        
        originabot_agent_hystory = state["originabot_agent_hystory"]
        logger.info("invocando al subagente")
        subagent_response = originabotdb_subagent.invoke(originabot_agent_hystory)
        originabot_agent_hystory = subagent_response["messages"]
        ai_message : AIMessage = subagent_response["messages"][-1]
        tool_message_subagent.content = ai_message.content
        result = tool_message_list + [tool_message_subagent]
        for msg in result:
                logger.info(f"{msg.pretty_repr()}")
        return {"messages":result, "originabot_agent_hystory":originabot_agent_hystory}
    

    def should_end(state : State) -> Literal[END, "tool_node_wrapper"]: # type: ignore
        logger.info("---"*4 + " tool_node_wrapper")
        # logger.info("=== should_end")
        last_ai_message : AIMessage = state["messages"][-1]
        if not last_ai_message.tool_calls:
            logger.info("END" + "\n"*5)
            return END
        logger.info("tool_node_wrapper" + "\n"*5)
        return "tool_node_wrapper"
    


    # ============================
    # COMPILACION DEL GRAFO
    # ============================

    builder = StateGraph(State)

    builder.add_node("ReAct_node", ReAct_node)
    builder.add_node("tool_node_wrapper", tool_node_wrapper)
    
    builder.add_edge(START, "ReAct_node")
    builder.add_conditional_edges("ReAct_node", should_end)
    builder.add_edge("tool_node_wrapper", "ReAct_node")

    return builder.compile()


