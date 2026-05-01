# Discord Echo Graph

Sistema que ingesta mensajes de Discord, los resume con un LLM y los inserta en un grafo de conocimiento (Neo4j + pgvector vía LightRAG). Expone un agente de chat (ReAct) que consulta ese grafo para responder preguntas sobre el contenido de Discord.

---

## Servicios

### DiscordEchoSaver

Fetcha mensajes, canales y usuarios de un servidor de Discord y los persiste en la base de datos principal (`edubotapp`). Los endpoints disponibles están en `src/api/v1/routers/fetchDiscordApi.py`.

---

### DiscordGraph

Procesa los mensajes guardados y construye el grafo de conocimiento. El pipeline debe ejecutarse **en el siguiente orden**:

#### Paso 1 — `chunking_messages.py`

`chunking_recursively_by_channel_id(channel_ids)` particiona los mensajes de cada canal en ventanas de tiempo de 2 a 4 semanas y crea los registros correspondientes en la tabla `channel_chronological_summary` (mínimo 50 mensajes por chunk).

#### Paso 2 — `prune_in_lightrag_status_from_summaries` y `sweep_pending_deletions`

Cuando el re-chunking fusiona chunks que ya estaban en LightRAG, esos chunks deben eliminarse del grafo antes de volver a insertarlos. `prune_in_lightrag_status_from_summaries` marca los chunks afectados para eliminación. Como la eliminación no es inmediata (LightRAG debe recalcular el grafo), `sweep_pending_deletions` debe ejecutarse repetidamente hasta confirmar que los chunks fueron eliminados consultando `src/lightrag_models.py`.

> **Importante:** no insertar chunks nuevos hasta que los chunks marcados para eliminación hayan sido confirmados como eliminados.

#### Paso 3 — `partition_summary`

Divide los chunks que aún no están en LightRAG y superan el tamaño máximo (100 mensajes), partiéndolos a la mitad.

#### Paso 4 — `make_all_pending_summaries`

Genera el resumen LLM de cada chunk que no esté en LightRAG y lo deja en estado `ready` en `channel_chronological_summary`. Los resúmenes filtran el ruido de conversaciones irrelevantes y concentran la información útil del canal.

#### Paso 5 — `insert_to_light_rag` y `sync_processed_lightrag_docs`

`insert_to_light_rag` envía los chunks en estado `ready` al servidor LightRAG, que construye el grafo y la base vectorial. Como el proceso es asíncrono y puede fallar por alta demanda del servidor, `sync_processed_lightrag_docs` consulta el estado y marca como `in_lightrag` los chunks ya procesados. Es normal re-ejecutar `insert_to_light_rag` sobre registros que fallaron.

---

### ChatEdubot

Agente de chat (LangGraph ReAct) con LightRAG como herramienta de recuperación. Está diseñado para responder preguntas sobre toda la información de Discord indexada.

> **Aviso:** si ya hay un bot desplegado con los mismos comandos de Discord, cambiar los comandos en este servicio para evitar conflictos.

---

## Servicio LightRAG (`docker-compose.lightrag.yml`)

Gestiona los embeddings, la construcción del grafo y la recuperación de documentos. Toda la información persiste en la base de datos vectorial (`rag`) y en Neo4j; el servicio en sí es stateless salvo por el volumen `metrics/` (creado automáticamente).

### Métricas

| Archivo | Columnas |
|---|---|
| `metrics/token_usage.csv` | `timestamp`, `modelo`, `prompt_tokens`, `completion_tokens`, `total_tokens` |
| `metrics/format_errors.csv` | `timestamp`, `chunk_id`, `tipo` (ENTITY/RELATION), `nombre`, `campos_encontrados`, `campos_esperados` |

### Limitaciones conocidas

- **Pérdida de información:** errores de formato en la salida del LLM provocan que algunos nodos y aristas no se inserten en el grafo, lo que reduce su precisión. Los casos quedan registrados en `format_errors.csv`.
- **Costo computacional:** insertar o eliminar documentos implica uso intensivo del LLM. Evaluar cuidadosamente la frecuencia de actualización del grafo.

---

## Restauración de bases de datos

El proyecto requiere tres bases de datos. A continuación los comandos para restaurarlas a partir de los dumps.

### PostgreSQL — `edubotapp` (Discord data)

```bash
docker exec -i edu-dulcinea-db pg_restore -U postgres -d edubotapp < data/eduuv3b.dump
```

### PostgreSQL — `rag` (LightRAG)

```bash
# Crear la base de datos primero
psql -U postgres -c "CREATE DATABASE rag;"

docker exec -i edu-dulcinea-db pg_restore -U postgres -d rag < data/google3.dump
```

### Neo4j — grafo de conocimiento

```bash
docker cp google3.cypher neo4j-db:/var/lib/neo4j/import

docker exec -it neo4j-db bash
cypher-shell -u neo4j -p <password> < /var/lib/neo4j/import/google3.cypher
```

Los archivos `docker-compose.neo4j.yaml` y `docker-compose.pgvector.yaml` contienen la configuración utilizada para desarrollo local. También es posible iniciar el sistema desde cero sin restaurar dumps.
