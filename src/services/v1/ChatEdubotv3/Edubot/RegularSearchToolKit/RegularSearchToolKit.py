from .retrive_messages import get_all_messages_chunks, get_all_messages_chunks_with_regex
from .generate_partial_response import  generate_partial_responses

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool, BaseTool
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List

import asyncio

class RetrivePartialResponsesToolKit:
    def __init__(self, llm : BaseChatModel, semaphore : asyncio.Semaphore, session : Session):
        self.llm = llm
        self.semaphore = semaphore
        self.session = session

    

    def _search_by_substring_keyword(self, key_word : str, query : str) -> str:
        try:
            chunks = get_all_messages_chunks(session=self.session, key_word=key_word)
            partials_responses = asyncio.run(
                generate_partial_responses(semaphore=self.semaphore, query=query, llm=self.llm, chunks=chunks)
            )
            return partials_responses
        except Exception as e:
            return f"Error: {e}"
    
    def _serach_by_exact_keyword(self, key_word : str, query : str) -> str:
        try:
            chunks = get_all_messages_chunks_with_regex(session=self.session, key_word=key_word)
            partials_responses = asyncio.run(
                generate_partial_responses(semaphore=self.semaphore, query=query, llm=self.llm, chunks=chunks)
            )
            return partials_responses
        except Exception as e:
            return f"Error: {e}"


    

    # -------------------
    # -------------------

    class RetrivePartialResponses(BaseModel):
        key_word : str = Field(
            description=(
                "Palabra clave a buscar directamente en los mensajes de Discord. "
                "Debe ser un término concreto y específico (nombre, concepto, proyecto, herramienta). "
                "Evita palabras muy frecuentes o genéricas para no recuperar cientos de mensajes irrelevantes."
            )
        )
        query : str = Field(
            description=(
                "Pregunta o consulta completa que el LLM responderá basándose en los mensajes de Discord "
                "que contienen la palabra clave y su contexto temporal. "
                "Escribe una oración clara y descriptiva con todo el detalle necesario para responder bien."
            )
        )


    # -------------------
    # -------------------

    def get_tools(self) -> List[BaseTool]:
        return [
            StructuredTool.from_function(
                name="search_by_substring_keyword",
                description=(
                    "Busca en la base de datos de mensajes crudos de Discord aquellos mensajes que contienen "
                    "`key_word` como subcadena (insensible a mayúsculas/minúsculas)."
                    "Por cada canal con coincidencias, recupera los mensajes en un rango de ±4 días alrededor "
                    "de cada coincidencia para capturar el contexto conversacional real; luego un LLM genera "
                    "una respuesta parcial por canal basada en esos mensajes y la `query`. "
                    "Al ser búsqueda por subcadena, 'python' también encontrará 'python3', 'pythonista', etc. "
                    "Úsala cuando necesites rastrear menciones específicas de un término directamente en los "
                    "mensajes del servidor, o cuando `query_lightrag` no tenga suficiente detalle sobre el tema. "
                    "Prefiere `search_by_exact_keyword` si quieres evitar falsos positivos por subcadena."
                ),
                func=self._search_by_substring_keyword,
                args_schema=self.RetrivePartialResponses
            ),
            StructuredTool.from_function(
                name="search_by_exact_keyword",
                description=(
                    "Busca en la base de datos de mensajes crudos de Discord aquellos mensajes que contienen "
                    "exactamente la palabra completa `key_word` (límites de palabra regex, insensible a "
                    "mayúsculas/minúsculas). A diferencia de `search_by_substring_keyword`, esta búsqueda NO "
                    "trae variantes ni fragmentos: 'LLM' encuentra 'LLM' pero NO 'RLLM', 'LLMs' ni 'FLLM'. "
                    "Por cada canal con coincidencias, recupera los mensajes en un rango de ±4 días alrededor "
                    "de cada coincidencia para capturar el contexto conversacional real; luego un LLM genera "
                    "una respuesta parcial por canal basada en esos mensajes y la `query`. "
                    "Úsala cuando la palabra clave sea un término técnico, sigla o nombre propio que no debe "
                    "confundirse con otras palabras que lo contengan como parte."
                ),
                func=self._serach_by_exact_keyword,
                args_schema=self.RetrivePartialResponses
            ),
        ]
    

    

if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from langchain_groq import ChatGroq

    from src import settings
    import asyncio
    
    # model="openai/gpt-oss-20b"
    model="openai/gpt-oss-120b"

    llm = ChatGroq(model=model, temperature=0.2, api_key=settings.GROQ_API_KEY)

    semaphore = asyncio.Semaphore(3)

    engine = create_engine(settings.DB_DISCORD_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()

    

    search_toolkit = RetrivePartialResponsesToolKit(llm=llm, semaphore=semaphore, session=session)
    tools = search_toolkit.get_tools()

    key_word = "Manhattan"
    query = "Cual es la respuesta oficial de la alcaldia al proyecto Manhattan"

    # print(tools)

    serach_by_exact_keyword = tools[1] 
    x = serach_by_exact_keyword.invoke({"key_word":key_word, "query":query})

    print(x)


"""
python3 -m src.services.v1.ChatEdubotv3.Edubot.RegularSearchToolKit.RegularSearchToolKit


"""




