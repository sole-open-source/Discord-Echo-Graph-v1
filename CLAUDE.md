# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord-Echo-Graph is a multi-service system that ingests Discord messages, chunks and summarizes them with an LLM, inserts summaries into a knowledge graph (LightRAG → Neo4j + pgvector), and exposes a ReAct chat agent that queries that graph to answer questions about Discord content.

## Running the System

**Start infrastructure (order matters):**
```bash
docker compose -f docker-compose.pgvector.yaml up -d      # PostgreSQL + pgvector on port 5434
docker compose -f docker-compose.neo4j.yaml up -d         # Neo4j on ports 7474/7687
docker compose -f docker-compose.lightrag.yml up -d       # LightRAG service on port 9621
```

**Start the FastAPI server:**
```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Run Discord saver standalone (without API):**
```bash
python3 -m src.services.v1.DiscordEchoSaver.discord_echo_saver_v1
```

**Run tests (manual API tests only):**
```bash
python3 test/api/v1/fetchDiscordApi.py
```

**vLLM local inference (GPU required):**
```bash
docker compose -f vLLM_service/docker-compose.yaml up -d  # Gemma 4 26B on GPUs 0+1, BGE-M3 embed on GPU 2
```

## Architecture

### Data Flow

```
Discord API
    → DiscordEchoSaver  (discord.py bot, saves raw messages to edubotapp DB)
    → DiscordGraph pipeline:
        1. chunking_messages.py   → creates channel_chronological_summary records (2-4 week windows)
        2. summary_chunks.py      → LLM summarizes each chunk
        3. lightrag_crud.py       → inserts summaries into LightRAG (builds Neo4j graph + pgvector VDB)
    → ChatEdubot (LangGraph ReAct agent) queries LightRAG → answers user questions
```

### Three Databases (all PostgreSQL, port 5434)

| Env var | Default | Purpose |
|---|---|---|
| `DB_NAME_DISCORD` | `edubotapp` | Raw Discord data + summaries |
| `DB_NAME_LIGHTRAG` | `rag` | LightRAG entities, relations, VDB chunks |
| `DB_NAME_EDUCHAT` | `educhat` | Chat sessions and message history |

Models: `src/discord_models.py`, `src/lightrag_models.py`, `src/chatedubot_models.py`  
Session/CRUD helpers: `src/database.py` (`CrudHelper` class wraps common SQLAlchemy patterns)

### Key Status Field

`channel_chronological_summary.status` drives the processing pipeline:
- `None` → chunk created, not yet summarized
- `'ready'` → LLM summary complete, not yet in LightRAG
- `'in_lightrag'` → fully processed and searchable
- `'pending_deletion'` → marked for removal from LightRAG (happens when chunks are merged/re-partitioned)

### DiscordGraph Pipeline (`src/services/v1/DiscordGraph/`)

The pipeline functions are called manually or via scheduler — there is no automatic trigger. Correct order:
1. `chunking_recursively_by_channel_id()` — partition messages into time windows
2. `prune_in_lightrag_status_from_summaries()` — remove obsolete `in_lightrag` records
3. `sweep_pending_deletions()` — poll LightRAG to confirm deletions
4. `partition_summary()` — split oversized chunks (>100 messages)
5. `make_all_pending_summaries()` — LLM summarization (3 concurrent calls via semaphore)
6. `insert_to_light_rag()` — POST summaries to LightRAG server
7. `sync_processed_lightrag_docs()` — mark as `in_lightrag`

### FastAPI (`src/api/main.py`, port 8000)

- `POST /fetchdiscord/channels` — sync guild channels (202, async background task)
- `POST /fetchdiscord/users` — sync guild members
- `POST /fetchdiscord/messages` — sync messages for given channel IDs
- `POST /educhat/newuser` — create user session
- `POST /educhat/newchat` — start conversation
- `POST /educhat/send` — send message, returns agent response

The Discord bot client (`DiscordEchoSaverBot`) is started on FastAPI startup and shared across requests via `app.state`.

### ChatEdubot (`src/services/v1/ChatEdubot/`)

LangGraph ReAct agent. `agent.py` builds the state graph; `toolkit.py` wraps LightRAG `/query` HTTP calls as LangChain tools (local / global / hybrid / naive search modes). `run_chat.py` reconstructs full LangChain message history from the `educhat` DB on each request and persists the new exchange back.

### LightRAG Service

External HTTP service (Docker). Key endpoints used by this codebase:
- `POST /documents/add` — insert a text chunk (triggers graph extraction + VDB indexing)
- `DELETE /documents/delete_document` — remove a chunk by doc ID
- `POST /query` — search (mode: `local` | `global` | `hybrid` | `naive`)

LightRAG uses **Gemini 2.5 Flash** for graph extraction and **Gemini Embedding 001** (1536-dim) for vectors. Alternative bindings (Groq, Ollama, Anthropic) are configurable via `.env`.

## Configuration

All settings loaded from `.env` via `src/settings.py`. Key variables:

```
# Databases
DB_USER, DB_PASS, DB_HOST, DB_PORT
DB_NAME_DISCORD, DB_NAME_LIGHTRAG, DB_NAME_EDUCHAT

# Discord
DISCORD_BOT_TOKEN
DULCINEA_DISCORD_BOT_TOKEN   # second bot for a different server

# LLM providers
GOOGLE_API_KEY
GROQ_API_KEY

# LightRAG
LIGHTRAG_SERVER_HOST, LIGHTRAG_SERVER_PORT
LLM_BINDING, LLM_MODEL, EMBEDDING_MODEL, EMBEDDING_DIM
```

Docker-compose files use `172.17.0.1` (Docker bridge host IP) for database connections from inside containers.

## Logging

`src/logging_config.py` — rotating file logs (5 MB max) written to `.logs/<SERVICE>/`. Each service gets its own logger via `setup_logger(service_name)`.

## Known Limitations (from README)

- LightRAG graph extraction has format errors (missing fields in LLM output) → some entities/relations are silently dropped, causing precision loss in search.
- Knowledge graph updates are LLM-intensive and expensive; update frequency must be chosen deliberately.
- Token usage and format errors are tracked in `./metrics/token_usage.csv` and `./metrics/format_errors.csv` (auto-created by LightRAG service).
