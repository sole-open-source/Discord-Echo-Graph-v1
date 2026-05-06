from typing import Literal, TypedDict, List

from langchain_core.tools import StructuredTool, BaseTool
from src import settings
from pydantic import BaseModel, Field
import httpx

from src.logging_config import get_logger
logger = get_logger(module_name="toolkit", DIR="queryAgent")

LIGHTRAG_URL = f"http://{settings.LIGHTRAG_SERVER_HOST}:{settings.LIGHTRAG_SERVER_PORT}"
HEADERS = {}

# Cliente persistente: reutiliza conexiones HTTP entre tool calls (keep-alive)
_http_client = httpx.Client(timeout=120)



class Reference(TypedDict):
    reference_id : str
    file_path : str


class QueryLightragResponse(TypedDict):
    response : str
    references : List[Reference]


class LightRagToolKit:
    def __init__(self):
        pass

    def _query_lightrag(self,
        query : str,
        mode : Literal["local", "global", "hybrid", "naive", "mix", "bypass"],
        ):
        PAYLOAD = {
            "query":query,
            "mode":mode,
            "top_k":40,
            "chunk_top_k":20,
            "max_entity_tokens":10000,
            "max_relation_tokens":12000,
            "max_total_tokens":40000,
            "enable_rerank":True,
            "include_references":True
        }

        logger.info(f"Llamando a LightRAG — url={LIGHTRAG_URL}/query mode={mode}")
        logger.debug(f"Query: {query}")
        try:
            response = _http_client.post(
                    f"{LIGHTRAG_URL}/query",
                    json=PAYLOAD,
                    headers=HEADERS,
                )
            logger.info(f"LightRAG respondió — status={response.status_code}")
            response.raise_for_status()
            data = response.json()
            response_preview = str(data.get("response", ""))[:200]
            n_refs = len(data.get("references", []))
            logger.info(f"LightRAG OK — {n_refs} referencias, respuesta (primeros 200 chars): {response_preview}")
            return data
        except httpx.TimeoutException as e:
            logger.error(f"LightRAG TIMEOUT después de 120s — url={LIGHTRAG_URL} mode={mode}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"LightRAG CONNECTION ERROR — no se pudo conectar a {LIGHTRAG_URL}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"LightRAG HTTP ERROR — status={e.response.status_code} body={e.response.text[:300]}")
            raise
        except Exception as e:
            logger.error(f"LightRAG error inesperado — {type(e).__name__}: {e}")
            raise
        

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
        query: str = Field(
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



    






    


    
    

