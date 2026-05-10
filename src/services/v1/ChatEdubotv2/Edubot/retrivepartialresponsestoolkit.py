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

    
    async def _get_partial_responses_from_key_word(self, key_word : str, query : str) -> str:
        chunks = get_all_messages_chunks(session=self.session, key_word=key_word)
        partials_responses = await generate_partial_responses(semaphore=self.semaphore, query=query, llm=self.llm, chunks=chunks)
        return partials_responses
    
    async def _get_partial_responses_from_exact_key_word(self, key_word : str, query : str) -> str:
        chunks = get_all_messages_chunks_with_regex(session=self.session, key_word=key_word)
        partials_responses = await generate_partial_responses(semaphore=self.semaphore, query=query, llm=self.llm, chunks=chunks)
        return partials_responses
    

    # -------------------
    # -------------------

    class RetrivePartialResponses(BaseModel):
        key_word : str = Field(description="")
        query : str = Field(description="")
        

    class RetrivePartialExactResponse(BaseChatModel):
        key_word : str = Field(description="")
        query : str = Field(description="")


    # -------------------
    # -------------------

    def get_tools(self) -> List[BaseTool]:
        return [
            StructuredTool.from_function(
                name="",
                description="",
                func=self._get_partial_responses_from_key_word,
                args_schema=self.RetrivePartialResponses
            ),
        ]
    

    

