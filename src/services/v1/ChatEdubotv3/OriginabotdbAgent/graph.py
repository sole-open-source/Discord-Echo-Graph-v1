
from src.logging_config import get_logger
from .postgrestoolkit import PostgresToolKit
from sqlalchemy.engine import Engine

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import RetryPolicy

from typing import TypedDict, Annotated, Sequence, Literal
from langgraph.graph import add_messages, END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.graph.state import CompiledStateGraph
from typing import List, Dict

from groq import BadRequestError as GroqBadRequestError
from groq import GroqError



logger = get_logger(module_name="DBchat", DIR="Agents")


def create_chat_agent(llm : BaseChatModel, engine : Engine, originabotdb_json : Dict[str, List[str]]) -> CompiledStateGraph:
    
    toolkit = PostgresToolKit(engine=engine, originabotdb_json=originabotdb_json)
    tools = toolkit.get_tools()
    logger.info(f"Hay {len(tools)} tools en el toolkit\n")

    llm_with_tools = llm.bind_tools(tools)

    class State(TypedDict):
        messages : Annotated[Sequence[BaseMessage], add_messages]
    
    tool_node = ToolNode(messages_key="messages", tools=tools)
    
    def ReAct_node(state : State) -> State:
        logger.info("---"*4 + " ReAct_node \n")
        #logger.info("=== ReAct_node")
        messages = state["messages"]
        try:
            ai_message = llm_with_tools.invoke(messages)
        except Exception as e:
            logger.error(f"Error: {e}")
            raise ValueError(f"Error: {e}")
        logger.info(f"\n {ai_message.pretty_repr()} \n\n")
        return {"messages":ai_message}



    def tool_node_wrapper(state : State) -> State:
        logger.info("---"*4 + " tool_node_wrapper\n")
        #logger.info("=== tool_node_wrapper")
        # tool_response será un dict como {"messages": [ToolMessage, ToolMessage, ...]}
        tool_responses = tool_node.invoke(state)
        for tool_response in tool_responses["messages"]:
            logger.info(f"{tool_response.pretty_repr()}\n")
        #logger.info("\n")
        return tool_responses
    


    def should_end(state : State) -> Literal["tool_node_wrapper",END]: # type: ignore
        logger.info("---"*4 + " tool_node_wrapper")
        #logger.info("=== should_end")
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            logger.info(f"tool_node_wrapper")
            return "tool_node_wrapper"
        logger.info("END")
        logger.info("\n"*10)
        return END
    

    builder = StateGraph(State)

    builder.add_node("ReAct_node", ReAct_node, retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0, retry_on=GroqError))
    # builder.add_node("ReAct_node", ReAct_node)
    builder.add_node("tool_node_wrapper", tool_node_wrapper)

    builder.add_edge(START, "ReAct_node")
    builder.add_conditional_edges("ReAct_node", should_end)
    builder.add_edge("tool_node_wrapper", "ReAct_node")

    graph = builder.compile()

    return graph




if __name__=="__main__":
    from src import settings
    from langchain_core.messages import SystemMessage, HumanMessage
    from .prompts import DB_AGENT_SYSTEM_PROMPT_3
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq
    import json

    from sqlalchemy import create_engine
    
    from pathlib import Path

    from src.logging_config import setup_base_logging
    setup_base_logging()

    # model = "gemini-2.0-flash"
    # llm = ChatGoogleGenerativeAI(model=model, temperature=0.5, api_key=settings.GOOGLE_API_KEY)

    model = "openai/gpt-oss-120b"
    llm = ChatGroq(model=model, temperature=0.2, api_key=settings.GROQ_API_KEY)

    root_dir = Path(__file__).resolve().parent
    # print(root_dir)
    path = root_dir / "originabotSKILL.md"
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

    path = root_dir / "originabot.json"
    with open(path, "r", encoding="utf-8") as f:
        originabotdb_json = json.load(f)


    chat = create_chat_agent(llm=llm, engine=engine, originabotdb_json=originabotdb_json)

    system_prompt = DB_AGENT_SYSTEM_PROMPT_3.format(top_n=15, description=description)
    messages = [SystemMessage(content=system_prompt)]
    while True:
        print("========================= Human Message =============================\n")
        human_message = input()
        if human_message=="exit":
            break
        human_message = HumanMessage(content=human_message)
        messages.append(human_message)
        response = chat.invoke({"messages":messages})
        messages = response["messages"]

    print("\n Fin del chat")


"""
python3 -m src.services.v1.ChatEdubotv3.OriginabotdbAgent.graph



Obtener la lista de proyectos de tipo 'minigrenja' (pequeñas granjas solares) con la mayor producción de energía. Necesito el nombre del proyecto, la ubicación (ciudad o región) y la energía total producida hasta la fecha, ordenada de mayor a menor. Asume que la tabla de proyectos se llama 'proyectos' con columnas 'id', 'nombre', 'tipo', 'ubicacion', y que la tabla de producción se llama 'produccion_energia' con columnas 'proyecto_id', 'energia_mwh' (energía acumulada en MWh). Realiza una consulta que sume la energía por proyecto y filtre por tipo='minigrenja', luego ordene los resultados descendente y devuelva los top 10.

Obtener la lista de proyectos de tipo 'minigrenja' (pequeñas granjas solares) con la mayor producción de energía. Necesito el nombre del proyecto, la ubicación (ciudad o región) y la energía total producida hasta la fecha, ordenada de mayor a menor. 

Count the total number of rows in the table minifarm_projectprice in the originabotdb database. Return the count as a single number with a clear label. 


"""