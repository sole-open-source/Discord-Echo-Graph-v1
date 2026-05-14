from typing import Literal, TypedDict, List

from langchain_core.tools import StructuredTool, BaseTool
from src import settings
from . import conf
import os
from pydantic import BaseModel, Field

from lightrag import LightRAG, QueryParam
from lightrag.llm.gemini import gemini_embed, gemini_model_complete
from lightrag.utils import EmbeddingFunc
from lightrag.utils import TokenTracker
import tiktoken
import asyncio

from sqlalchemy.orm import Session
from src.chatedubot_models import UsageMetadata as UsageMetadataRecord, MetaDataTask

from src.logging_config import get_logger
logger = get_logger(module_name="lightrag_tool", DIR="Agent")


GOOGLE_API_KEY = settings.GOOGLE_API_KEY

os.environ["POSTGRES_HOST"] = settings.DB_HOST
os.environ["POSTGRES_PORT"] = str(settings.DB_PORT)
os.environ["POSTGRES_USER"] = settings.DB_USER
os.environ["POSTGRES_PASSWORD"] = settings.DB_PASS
os.environ["POSTGRES_DATABASE"] = settings.DB_NAME_LIGHTRAG

os.environ["NEO4J_URI"] = settings.NEO4J_URI
os.environ["NEO4J_USERNAME"] = settings.NEO4J_USERNAME
os.environ["NEO4J_PASSWORD"] = settings.NEO4J_PASSWORD

os.environ["LLM_MODEL"] = conf.LLM_MODEL


class EmbeddingTokenTracker:
    def __init__(self):
        self.total_tokens = 0
        self.call_count = 0
        # cl100k_base es una buena aproximación para modelos Gemini
        self._enc = tiktoken.get_encoding("cl100k_base")

    def get_usage(self):
        return {"total_tokens": self.total_tokens, "call_count": self.call_count}


def make_tracked_embed(base_func, embed_tracker: EmbeddingTokenTracker):
    async def tracked(*args, **kwargs):
        texts = args[0] if args else kwargs.get("texts", [])
        for t in texts:
            embed_tracker.total_tokens += len(embed_tracker._enc.encode(t))
        embed_tracker.call_count += 1
        return await base_func(*args, **kwargs)
    return tracked




class Reference(TypedDict):
    reference_id : str
    file_path : str


class QueryLightragResponse(TypedDict):
    response : str
    references : List[Reference]



class LightRagToolKit:
    def __init__(self, session: Session):
        self.session = session
        self._message_id: int | None = None

    def set_message_id(self, message_id: int | None) -> None:
        self._message_id = message_id

    async def _aquery_lightrag(self, rag: LightRAG, mode: str, question: str) -> str:
        return await rag.aquery(
            question,
            param=QueryParam(
                mode=mode,
                top_k=conf.TOP_K,
                chunk_top_k=conf.CHUNK_TOP_K,
                max_total_tokens=conf.MAX_TOTAL_TOKENS,
            ),
        )
    

    async def _lightrag_backend(self, mode : str, question : str):
        llm_tracker = TokenTracker()
        embed_tracker = EmbeddingTokenTracker()

        gemini_embedding = EmbeddingFunc(
            embedding_dim=conf.EMBED_DIM,
            max_token_size=conf.EMBED_MAX_TOKEN_SIZE,
            model_name=conf.EMBED_MODEL,
            send_dimensions=True,
            func=gemini_embed.func,
        )

        rag = LightRAG(
            working_dir="/tmp/lightrag_retriver", 
            llm_model_func=gemini_model_complete,
            llm_model_name=conf.LLM_MODEL,
            embedding_func=gemini_embedding,
            kv_storage=conf.LIGHTRAG_KV_STORAGE,
            doc_status_storage=conf.LIGHTRAG_DOC_STATUS_STORAGE,
            vector_storage=conf.LIGHTRAG_VECTOR_STORAGE,
            graph_storage=conf.LIGHTRAG_GRAPH_STORAGE,
            llm_model_kwargs={"token_tracker": llm_tracker},
        )

        await rag.initialize_storages()

        result = await self._aquery_lightrag(rag=rag, mode=mode, question=question)

        usage = llm_tracker.get_usage()
        emb_usage = embed_tracker.get_usage()

        logger.info(f"Prompt tokens:     {usage['prompt_tokens']}")
        logger.info(f"Completion tokens: {usage['completion_tokens']}")
        logger.info(f"Total tokens:      {usage['total_tokens']}")
        logger.info(f"Embedding tokens (aprox): {emb_usage['total_tokens']}")
        logger.info(f"Embedding calls:          {emb_usage['call_count']}")

        try:
            record = UsageMetadataRecord(
                message_id=self._message_id,
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
                model_name=conf.LLM_MODEL,
                task=MetaDataTask.LIGHTRAG,
            )
            self.session.add(record)
            self.session.commit()
            logger.info(f"UsageMetadata guardado: message_id={self._message_id}, task=LIGHTRAG")
        except Exception as e:
            logger.error(f"Error guardando UsageMetadata: {e}")
            self.session.rollback()

        return result
    



    def _query_lightrag(self,
        question : str,
        mode : Literal["local", "global", "hybrid", "naive", "mix", "bypass"],
        ) -> str:
        try:
            result = asyncio.run(self._lightrag_backend(mode=mode, question=question))
            return result
        except Exception as e:
            logger.error(f"error en _query_lightrag: \n {e}")
            return f"error: \n {e}"
        

    # -------------------
    # -------------------
    

    class QueryLightRag(BaseModel):
        mode: Literal["local", "global", "hybrid", "naive", "mix"] = Field(
            description=(
                "Search mode to use in the LightRAG knowledge graph. Choose based on the type of question:\n"
                "- 'local': Retrieves context around specific entities (people, concepts, places, facts). "
                "Best for precise, fact-based questions about a known subject.\n"
                "- 'global': Retrieves high-level summaries and community-level knowledge. "
                "Best for broad questions about trends, overviews, or cross-document themes.\n"
                "- 'hybrid': Combines local and global retrieval. Use when the question needs both "
                "specific detail and broad context.\n"
                "- 'naive': Direct vector similarity search without graph traversal. "
                "Useful for simple semantic lookups when graph structure is not needed.\n"
                "- 'mix': Integrates the knowledge graph with vector search. "
                "Recommended when a reranker is configured — generally the highest-quality mode."
            )
        )
        question: str = Field(
            description=(
                "Natural language question or search query to run against the indexed document knowledge base. "
                "Write a complete, descriptive sentence that captures exactly what information is needed. "
                "The more specific and contextual the query, the better the retrieval quality. "
                "Examples: 'What are the installation requirements for the system?' or "
                "'What procedures exist for handling billing errors?'"
            )
        )


    # -------------------
    # -------------------


    def get_tools(self) -> List[BaseTool]:
        tools = [
            StructuredTool.from_function(
                name="query_lightrag",
                description=(
                    "Query the LightRAG knowledge base built from indexed documents. "
                    "Use this tool whenever you need to answer questions grounded in specific documents, "
                    "retrieve detailed information about topics covered in the knowledge base, "
                    "or find supporting context and references from the source material. "
                    "Returns an LLM-generated answer along with references to the source documents."
                ),
                func=self._query_lightrag,
                args_schema=self.QueryLightRag,
            )
        ]

        return tools


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    _session = MySession()

    toolkit = LightRagToolKit(session=_session)
    tools = toolkit.get_tools()

    query_lightrag = tools[0]

    key_word = "Manhattan"
    mode = "local"
    question = "Cual es la respuesta oficial de la alcaldia al proyecto Manhattan"


    x = query_lightrag.invoke({"question":question, "mode":mode})
    print(x)

    pass


"""
python3 -m src.services.v1.ChatEdubotv3.Edubot.LightRagToolKit



"""