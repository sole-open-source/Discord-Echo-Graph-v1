# AGENTS.md for Discord-Echo-Graph-v1 repository
## Introduction
This file provides high-signal, repo-specific guidance for working with the Discord-Echo-Graph-v1 repository.

## Developer Commands
* Run infrastructure: `docker compose -f docker-compose.pgvector.yaml up -d`, `docker compose -f docker-compose.neo4j.yaml up -d`, `docker compose -f docker-compose.lightrag.yml up -d`
* Start FastAPI server: `python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`
* Run Discord saver standalone: `python3 -m src.services.v1.DiscordEchoSaver.discord_echo_saver_v1`
* Run tests: `python3 test/api/v1/fetchDiscordApi.py`

## Test and Lint
* Run lint and typecheck commands: `npm run lint`, `npm run typecheck`

## Architecture
* Data flow: Discord API -> DiscordEchoSaver -> DiscordGraph pipeline -> ChatEdubot
* Databases: edubotapp (raw Discord data), rag (LightRAG entities and relations), educhat (chat sessions and message history)

## Conventions
* Python code style: PEP 8
* Commit message style: imperative, brief summary

## Environment
* Required environment variables: DB_USER, DB_PASS, DB_HOST, DB_PORT, DISCORD_BOT_TOKEN, GOOGLE_API_KEY, GROQ_API_KEY

## LightRAG Service
* LightRAG server host and port: LIGHTRAG_SERVER_HOST, LIGHTRAG_SERVER_PORT