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
        chunks = get_all_messages_chunks(session=self.session, key_word=key_word)
        partials_responses = asyncio.run(
            generate_partial_responses(semaphore=self.semaphore, query=query, llm=self.llm, chunks=chunks)
        )
        return partials_responses
    
    def _serach_by_exact_keyword(self, key_word : str, query : str) -> str:
        chunks = get_all_messages_chunks_with_regex(session=self.session, key_word=key_word)
        partials_responses = asyncio.run(
            generate_partial_responses(semaphore=self.semaphore, query=query, llm=self.llm, chunks=chunks)
        )
        return partials_responses


    

    # -------------------
    # -------------------

    class RetrivePartialResponses(BaseModel):
        key_word : str = Field(description="palabra clave a buscar")
        query : str = Field(description="consulta")
        

    class RetrivePartialExactResponse(BaseChatModel):
        key_word : str = Field(description="")
        query : str = Field(description="")


    # -------------------
    # -------------------

    def get_tools(self) -> List[BaseTool]:
        return [
            StructuredTool.from_function(
                name="_search_by_substring_keyword",
                description=(
                    "Busaca entre los mensajes de discord aquellos mensajes que tienen una subcadena `key_word`, la busqueda es incensitivo a mayusculas y minusculas"
                    "para cada uno de estos mensaje se recuperan los mensjaes cercano a este y un modelo de lenguaje hace una respuesta basado en los mensjaes cercanos y el mensjae que contiene la subcadena y la `query`"
                ),
                func=self._search_by_substring_keyword,
                args_schema=self.RetrivePartialResponses
            ),
            StructuredTool.from_function(
                name="",
                description=(
                    "Busaca entre los mensajes de discord aquellos mensajes que tienen exactamente la palabra `key_word`, la busqueda es incensitivo a mayusculas y minusculas"
                    "para cada uno de estos mensaje se recuperan los mensjaes cercano a este y un modelo de lenguaje hace una respuesta basado en los mensjaes cercanos y el mensjae que contiene la subcadena y la `query`"
                ),
                func=self._serach_by_exact_keyword,
                args_schema=self.RetrivePartialResponses
            ),
        ]
    

    

