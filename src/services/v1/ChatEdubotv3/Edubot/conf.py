SUBAGENT_NAME = "invoke_Originabotdb_subagent"

# ============================================
# Lightrag tool
# ============================================



LLM_MODEL    = "gemini-2.5-flash"

EMBED_DIM    = 1536
EMBED_MODEL  = "gemini-embedding-001"
EMBED_MAX_TOKEN_SIZE = 8000


TOP_K = 60
CHUNK_TOP_K = 20
MAX_TOTAL_TOKENS = 30000

LIGHTRAG_KV_STORAGE="PGKVStorage"
LIGHTRAG_DOC_STATUS_STORAGE="PGDocStatusStorage"
LIGHTRAG_VECTOR_STORAGE="PGVectorStorage"
LIGHTRAG_GRAPH_STORAGE="Neo4JStorage"


# ============================================
# ...
# ============================================
