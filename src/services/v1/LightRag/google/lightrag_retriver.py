import os

from src import settings
from . import conf

from lightrag import LightRAG, QueryParam
from lightrag.llm.gemini import gemini_embed, gemini_model_complete
from lightrag.utils import EmbeddingFunc

import asyncio
from lightrag.utils import TokenTracker


GOOGLE_API_KEY = settings.GOOGLE_API_KEY

# LightRAG reads credentials from os.environ, not from Python variables.
# Map our settings names to the names each storage backend expects.
os.environ["POSTGRES_HOST"] = settings.DB_HOST
os.environ["POSTGRES_PORT"] = str(settings.DB_PORT)
os.environ["POSTGRES_USER"] = settings.DB_USER
os.environ["POSTGRES_PASSWORD"] = settings.DB_PASS
os.environ["POSTGRES_DATABASE"] = settings.DB_NAME_LIGHTRAG

os.environ["NEO4J_URI"] = settings.NEO4J_URI
os.environ["NEO4J_USERNAME"] = settings.NEO4J_USERNAME
os.environ["NEO4J_PASSWORD"] = settings.NEO4J_PASSWORD

os.environ["LLM_MODEL"] = conf.LLM_MODEL




import tiktoken

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





async def query_once(rag: LightRAG, mode: str, question: str) -> str:
    return await rag.aquery(
        question,
        param=QueryParam(
            mode=mode,
            top_k=conf.TOP_K,
            chunk_top_k=conf.CHUNK_TOP_K,
            max_total_tokens=conf.MAX_TOTAL_TOKENS,
        ),
    )



async def retrieve_context(rag: LightRAG, mode: str, question: str) -> str:
    return await rag.aquery(
        question,
        param=QueryParam(
            mode=mode,
            top_k=conf.TOP_K,
            chunk_top_k=conf.CHUNK_TOP_K,
            max_total_tokens=conf.MAX_TOTAL_TOKENS,
            only_need_context=True,  # <-- retorna el contexto crudo, no llama al LLM
        ),
    )


# Desventaja: recupera del grafo/VDB dos veces (doble latencia, doble costo de embedding).
async def query_with_context(rag: LightRAG, mode: str, question: str):
    context = await rag.aquery(
        question,
        param=QueryParam(mode=mode, top_k=conf.TOP_K, chunk_top_k=conf.CHUNK_TOP_K,
                        max_total_tokens=conf.MAX_TOTAL_TOKENS, only_need_context=True),
    )                    
    response = await rag.aquery(
        question,
        param=QueryParam(mode=mode, top_k=conf.TOP_K, chunk_top_k=conf.CHUNK_TOP_K,
                        max_total_tokens=conf.MAX_TOTAL_TOKENS),
    )
    return {"response": response, "context": context}



async def query_with_context(rag: LightRAG, mode: str, question: str):
    prompt = await rag.aquery(
        question,
        param=QueryParam(mode=mode, top_k=conf.TOP_K, chunk_top_k=conf.CHUNK_TOP_K,
                        max_total_tokens=conf.MAX_TOTAL_TOKENS, only_need_prompt=True),
    )
    response = await rag.aquery(
        question,
        param=QueryParam(mode=mode, top_k=conf.TOP_K, chunk_top_k=conf.CHUNK_TOP_K,
                        max_total_tokens=conf.MAX_TOTAL_TOKENS),
    )
    return {"response": response, "prompt_with_context": prompt}





async def main(mode : str, question : str):

    embed_tracker = EmbeddingTokenTracker()

    gemini_embedding = EmbeddingFunc(
        embedding_dim=conf.EMBED_DIM,
        max_token_size=conf.EMBED_MAX_TOKEN_SIZE,
        model_name=conf.EMBED_MODEL,
        send_dimensions=True,
        #func=gemini_embed.func,
        func=make_tracked_embed(gemini_embed.func, embed_tracker),
    )

    tracker = TokenTracker()

    rag = LightRAG(
        working_dir="/tmp/lightrag_retriver",
        llm_model_func=gemini_model_complete,
        llm_model_name=conf.LLM_MODEL,
        embedding_func=gemini_embedding,
        kv_storage=conf.LIGHTRAG_KV_STORAGE,
        doc_status_storage=conf.LIGHTRAG_DOC_STATUS_STORAGE,
        vector_storage=conf.LIGHTRAG_VECTOR_STORAGE,
        graph_storage=conf.LIGHTRAG_GRAPH_STORAGE,
        llm_model_kwargs={"token_tracker": tracker}
    )

    await rag.initialize_storages()

    usage = tracker.get_usage()
    # tracker.get_usage() te da un dict con prompt_tokens, completion_tokens, total_tokens y call_count acumulados de todas las llamadas al LLM que hizo aquery().
    response = await query_once(rag=rag, mode=mode, question=question)

    print("="*60)

    print(f"Prompt tokens:     {usage['prompt_tokens']}")
    print(f"Completion tokens: {usage['completion_tokens']}")
    print(f"Total tokens:      {usage['total_tokens']}")
    print(f"LLM calls:         {usage['call_count']}")


    emb_usage = embed_tracker.get_usage()

    print(f"Embedding tokens (aprox): {emb_usage['total_tokens']}")
    print(f"Embedding calls:          {emb_usage['call_count']}")

    
    print("="*60)
    
    return response



if __name__ == "__main__":
    question = "Cual es la respuesta oficial de la alcaldia al proyecto Manhattan "
    mode = "local"
    response = asyncio.run(main(mode=mode, question=question))
    print("============================================================")
    print(response)


"""
python3 -m src.services.v1.LightRag.google.lightrag_retriver



"""