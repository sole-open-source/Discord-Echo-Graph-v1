from src.logging_config import get_logger
from .conf import SUBAGENT_NAME
from .LightRagToolKit import LightRagToolKit
from .OriginabotdbToolKit import OriginabotdbSubAgentToolKit
from .RegularSearchToolKit.RegularSearchToolKit import RetrivePartialResponsesToolKit

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import add_messages, END, START, StateGraph
from langgraph.prebuilt import ToolNode

from typing import TypedDict, List, Annotated, Literal, Dict
from sqlalchemy.orm import Session
import asyncio

from src.chatedubot_models import UsageMetadata as UsageMetadataRecord, MetaDataTask, EduChatLogs


logger = get_logger(module_name="chat_edubot", DIR="Agent")


class CustomDict(TypedDict):
    subagent : CompiledStateGraph
    state_name : str



class SubAgentToolMessageDict(TypedDict):
    calls : int
    tool_message : ToolMessage
    subagent : CompiledStateGraph
    state_name : str


class StructureToolMessage(TypedDict):
    regular_tool_response : List[ToolMessage]
    subagent_tool_response : Dict[str, SubAgentToolMessageDict]
    


def structure_tool_message(tool_responses : List[ToolMessage], subagent_dict : Dict[str, CustomDict]) -> StructureToolMessage:
    """
    Nota, aqui las keys de subagent_dict deben coincidir con los nombres de las tools que activan la invocacion del agente

    """

    regular_tool_response = []
    subagent_tool_response = {}
    for msg in tool_responses:
        if msg.name in subagent_dict:
            if msg.name not in subagent_tool_response:
                subagent_tool_response[msg.name] = {"calls":1, "tool_message":msg, "subagent":subagent_dict[msg.name]["subagent"], "state_name":subagent_dict[msg.name]["state_name"]}
            else:
                x = subagent_tool_response[msg.name]
                x["calls"] += 1
        else:
            regular_tool_response.append(msg)

    return {"regular_tool_response":regular_tool_response, "subagent_tool_response":subagent_tool_response}


    


# =========================================================================
# =========================================================================





def create_chat_edubot(llm : BaseChatModel, subagent_dict : Dict[str, CustomDict], session : Session, educhat_session : Session, semaphore : asyncio.Semaphore) -> CompiledStateGraph:

    # ==========================
    # Tools
    # ==========================

    lightrag_toolkit = LightRagToolKit(session=educhat_session)
    lightrag_tools = lightrag_toolkit.get_tools()

    originabotdb_subagent_toolkit = OriginabotdbSubAgentToolKit()
    originabot_tools = originabotdb_subagent_toolkit.get_tools()

    retrive_toolkit = RetrivePartialResponsesToolKit(llm=llm, session=session, educhat_session=educhat_session, semaphore=semaphore)
    retrive_tools = retrive_toolkit.get_tools()


    tools = lightrag_tools + originabot_tools + retrive_tools
    logger.info(f"hay {len(tools)} tools")
    llm_with_tools = llm.bind_tools(tools=tools)

    _model_name = getattr(llm, "model_name", None) or getattr(llm, "model", None)

    # =========================
    # Estados del grafo
    # =========================

    class State(TypedDict):
        messages : Annotated[List[BaseMessage], add_messages]
        # originabot_agent_name : str | None
        originabot_agent_history : List[BaseMessage]
        current_message_id : int | None
        current_chat_id : int | None

    def _log(chat_id: int | None, msg: str) -> None:
        logger.info(msg)
        if chat_id is not None:
            educhat_session.add(EduChatLogs(chat_id=chat_id, log=msg))
            educhat_session.commit()

    
    tool_invoker = ToolNode(messages_key="messages", tools=tools)

    # ===================
    # Nodos del grafo
    # ===================

    def ReAct_node(state : State) -> State:
        chat_id = state.get("current_chat_id")
        _log(chat_id, "---"*4 + " ReAct_node")
        messages = state["messages"]
        try:
            ai_message = llm_with_tools.invoke(messages)
            _log(chat_id, ai_message.pretty_repr())
        except Exception as e:
            logger.error(f"Error en ReAct_node: \n {e}")
            raise ValueError(f"Error: \n {e}")

        usage = ai_message.usage_metadata
        if usage:
            try:
                record = UsageMetadataRecord(
                    message_id=state.get("current_message_id"),
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    model_name=_model_name,
                    task=MetaDataTask.EDUBOT,
                )
                educhat_session.add(record)
                educhat_session.commit()
                _log(chat_id, f"UsageMetadata guardado: message_id={state.get('current_message_id')}, task=EDUBOT")
            except Exception as e:
                logger.error(f"Error guardando UsageMetadata: {e}")
                educhat_session.rollback()

        return {"messages":ai_message}
        
    

    def tool_node_wrapper(state : State) -> State:
        # logger.info("=== tool_node_wrapper")
        chat_id = state.get("current_chat_id")
        _log(chat_id, "---"*4 + " tool_node_wrapper")
        current_message_id = state.get("current_message_id")
        lightrag_toolkit.set_message_id(current_message_id)
        lightrag_toolkit.set_chat_id(chat_id)
        retrive_toolkit.set_message_id(current_message_id)
        retrive_toolkit.set_chat_id(chat_id)
        tool_responses_ditc = tool_invoker.invoke(state) # {"messages" : [ToolMessage, ToolMessage ...]}
        _log(chat_id, "tools invocadas")

        tool_response : List[ToolMessage] = tool_responses_ditc["messages"]
        _log(chat_id, "structure_tool_message")
        structure_dict = structure_tool_message(tool_responses=tool_response, subagent_dict=subagent_dict)

        regular_tool_response = structure_dict["regular_tool_response"]
        subagent_tool_response = structure_dict["subagent_tool_response"]
        
        if not subagent_tool_response:
            _log(chat_id, "Caso 1. No se invoco ningun subagente")
            for msg in tool_response:
                _log(chat_id, msg.pretty_repr())
            return {"messages":regular_tool_response}
        
        result = []
        response = {"messages":None}
        for key in subagent_tool_response:
            data = subagent_tool_response[key]
            calls = data["calls"]
            if calls > 1:
                _log(chat_id, f"Caso 2. Error no puedes invocar a subagente: {key} mas de 1 vez a la vez")
                tool_message = data["tool_message"].content = f"Erros, no puedes invocar el subagente {key} mas de una vez a la vez"
                result.append(tool_message)
            else:
                _log(chat_id, f"Caso 3. invocando al subagente {key}")
                tool_message = data["tool_message"]
                to_do = tool_message.content
                state_name = data["state_name"]
                subagent_history : List[BaseMessage] = state[state_name]
                subagent_history.append(HumanMessage(content=to_do))
                
                subagent = data["subagent"]
                subagent_response = subagent.invoke({"messages": subagent_history})
                subagent_history = subagent_response["messages"]

                ai_message : AIMessage = subagent_response["messages"][-1]
                tool_message.content = ai_message.content
                result.append(tool_message)
                response[state_name] = subagent_history
            
        final_tool_response = regular_tool_response + result
        response["messages"] = final_tool_response
        for msg in final_tool_response:
            _log(chat_id, msg.pretty_repr())

        return response

            

        
        


    def should_end(state : State) -> Literal[END, "tool_node_wrapper"]: # type: ignore
        chat_id = state.get("current_chat_id")
        _log(chat_id, "---"*4 + " should_end")
        # logger.info("=== should_end")
        last_ai_message : AIMessage = state["messages"][-1]
        if not last_ai_message.tool_calls:
            _log(chat_id, "END")
            return END
        _log(chat_id, "tool_node_wrapper")
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




if __name__ == "__main__":

    from src import settings
    from langchain_core.messages import SystemMessage, HumanMessage
    from ..OriginabotdbAgent.prompts import DB_AGENT_SYSTEM_PROMPT_3
    from .prompts import EDUBOT_SYSTEM_PROMPT_1
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq
    import json
    import asyncio

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from ..OriginabotdbAgent.graph import create_chat_agent
    
    from pathlib import Path

    import conf

    from src.logging_config import setup_base_logging
    setup_base_logging()

    # model = "gemini-2.0-flash"
    # llm = ChatGoogleGenerativeAI(model=model, temperature=0.5, api_key=settings.GOOGLE_API_KEY)

    model = "openai/gpt-oss-120b"
    llm = ChatGroq(model=model, temperature=0.2, api_key=settings.GROQ_API_KEY)

    root_dir = Path(__file__).resolve().parent.parent
    # print(root_dir)
    path = root_dir / "OriginabotdbAgent" / "originabotSKILL.md"
    with open(path, "r", encoding="utf-8") as f:
        description = f.read()
    
    # print(description)

    DB_USER = "postgres"
    DB_PASS = "postgres"
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "originabotdb"

    conn_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(conn_string)

    path = root_dir / "OriginabotdbAgent" / "originabot.json"
    with open(path, "r", encoding="utf-8") as f:
        originabotdb_json = json.load(f)
    
    educhat_engine_sub = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    EduchatSessionSub = sessionmaker(bind=educhat_engine_sub)
    educhat_session_sub = EduchatSessionSub()

    originabot_agent = create_chat_agent(llm=llm, engine=engine, originabotdb_json=originabotdb_json, educhat_session=educhat_session_sub)

    subagent_dict = {
        conf.ORIGINABOT_SUBAGENT_NAME : {"state_name":"originabot_agent_history", "subagent":originabot_agent}
    }

    semaphore = asyncio.Semaphore(3)

    discord_engine = create_engine(settings.DB_DISCORD_CONN_STRING)
    DiscordSession = sessionmaker(bind=discord_engine)
    session = DiscordSession()

    educhat_engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    EduchatSession = sessionmaker(bind=educhat_engine)
    educhat_session = EduchatSession()

    edubot = create_chat_edubot(llm=llm, subagent_dict=subagent_dict, semaphore=semaphore, session=session, educhat_session=educhat_session)
    

    messages = [SystemMessage(content=EDUBOT_SYSTEM_PROMPT_1)]

    originabot_system_message = DB_AGENT_SYSTEM_PROMPT_3.format(top_n=15, description=description)
    originabot_agent_hystory = [SystemMessage(content=originabot_system_message)]
    

    while True:
        print("========================= Human Message =============================\n")
        human_message = input()
        if human_message=="exit":
            break
        human_message = HumanMessage(content=human_message)
        messages.append(human_message)
        response = edubot.invoke({"messages":messages, "originabot_agent_history":originabot_agent_hystory})
        messages = response["messages"]
        originabot_agent_hystory = response["originabot_agent_history"]
        print("\n"*10)
        print(type(originabot_agent_hystory))
        print(len(originabot_agent_hystory))
        for msg in originabot_agent_hystory:
            logger.debug(f"{type(msg.pretty_repr())}")
            logger.debug(f"{msg}")

    print("\n Fin del chat")




"""
python3 -m src.services.v1.ChatEdubotv3.Edubot.graph



"""