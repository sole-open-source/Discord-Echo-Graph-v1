from .retrive_messages import MessageChunk # TODO: no typear todo con esto
from .prompts import PROMPT_CHANNEL_MESSAGES_1

from langchain_core.language_models.chat_models import BaseChatModel
from typing import List, TypedDict, Dict, Any, Optional
from sqlalchemy.orm import Session

import asyncio

from src.logging_config import get_logger
logger = get_logger(module_name="parsial_response", DIR="toolkit_rs")




class DataChunk(TypedDict):
    channel_id : int
    channel_name : str
    server_name : str
    start_time : str
    end_time : str
    


class ProccesSingleChunk(TypedDict):
    partial_response : str
    usage_metadata : Dict[str, Any]
    data_chunk : DataChunk

async def process_single_chunk(llm : BaseChatModel, semaphore : asyncio.Semaphore, prompt : str, data_chunk : MessageChunk) -> ProccesSingleChunk:
    async with semaphore:
        try:
            ai_message = await llm.ainvoke(prompt)
            # print(f"usage_metadata: {ai_message.usage_metadata}, \n\n numero de caracteres: {len(ai_message.content)} \n\n\n")
            return {"partial_response":ai_message.content, "usage_metadata":ai_message.usage_metadata, "data_chunk":data_chunk}
        except Exception as e:
            logger.info(f"=== process_single_chunk")
            logger.error(f"error procesando los mensjes recuperados del canal con id {data_chunk['channel_id']}: \n {e} \n\n")
            return None



async def generate_partial_responses(semaphore : asyncio.Semaphore, query : str, llm : BaseChatModel, chunks : List[MessageChunk], max_chunks : int = 50) -> str:
    tasks = [
        process_single_chunk(
            llm=llm,
            semaphore=semaphore,
            prompt=PROMPT_CHANNEL_MESSAGES_1.format(query=query, messages=d.get("fianl_messages"), channel_name=d.get("channel_name")),
            data_chunk={
                "channel_id":d.get("channel_id"),
                "channel_name":d.get("channel_name"),
                "server_name":d.get("server_name"),
                "start_time":d.get("start_time"),
                "end_time":d.get("end_time")
            }
        )
        for d in chunks
    ]
    logger.info(f"Se van a generar {len(tasks)} sub respuestas")
    if len(tasks) >= max_chunks:
        return "Error, Se ha encontrado muchos canales de discord de texto extraidos de discord recuperados por la palabra clave `key_word`. Usar una palabra clave menos frecuente"

    if not tasks:
        raise ValueError("chunks es una lista vacia")
    
    # TODO: ir contando los tokens gastados
    count = 0
    input_tokens, output_tokens = 0, 0
    results = await asyncio.gather(*tasks)
    response = []

    for r in results:
        if r:
            partial_response = r.get("partial_response")
            usage_metadata = r.get("usage_metadata")    
            data_chunk = r.get("data_chunk")

            title = f"# Nombre del server de discord: {data_chunk.get("server_name")} Nombre del canal: {data_chunk.get("channel_name")} Fecha: desde {data_chunk.get("start_time")} hasta {data_chunk.get("end_time")}"
            response.append("\n\n".join([title, partial_response, "---"]))

    return "\n\n\n\n".join(response)

            


    
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src import discord_models as models
    from src import settings

    from .retrive_messages import get_all_messages_chunks
    from langchain_groq import ChatGroq
    from src import settings
    import asyncio

    from pathlib import Path
    root_dir = Path(__file__).resolve().parent


    engine = create_engine(settings.DB_DISCORD_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()

    key_word = "Manhattan"
    query = "Cual es la respuesta oficial de la alcaldia al proyecto Manhattan"
    chunks = get_all_messages_chunks(session=session, key_word=key_word)

    semaphore = asyncio.Semaphore(3)

    model="openai/gpt-oss-20b"
    llm = ChatGroq(model=model, temperature=0.2, api_key=settings.GROQ_API_KEY)


    response = asyncio.run(generate_partial_responses(semaphore=semaphore, query=query, llm=llm, chunks=chunks))
    print(response)




"""
python3 -m src.services.v1.ChatEdubotv2.Edubot.generate_partial_response


"""