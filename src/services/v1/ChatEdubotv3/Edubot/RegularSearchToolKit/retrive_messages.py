from src import discord_models as models
from sqlalchemy.orm import Session
from typing import TypedDict, List, Dict
from datetime import datetime, timedelta
from sqlalchemy import or_
import re

from src.logging_config import get_logger
logger = get_logger(module_name="retrive_message", DIR="Agent")



class MessagesKeyWord(TypedDict):
    message_id : int
    message_create_at : datetime


def fetch_messages_by_keyword(session: Session, key_word: str, max_retrive_messages : int = 300) -> Dict[int, List[MessagesKeyWord]]:
    logger.info("=== fetch_messages_by_keyword")
    """
    Recupera los registros de DiscordMessages cuyo content contenga una subcadena `key_word` y no necesariamente la `key_word` sola.

    Retorna un diccionario asi:

    {
        channel_id : [{message_id : id, message_create_at : datetime} ... ]
        ...generate_partial_response
    }
    """

    messages_records = session.query(models.DiscordMessage).filter(
        models.DiscordMessage.content.ilike(f'%{key_word}%')
    ).all()
    logger.info(f"Se ha recuperado {len(messages_records)} ilike {key_word}")

    if not messages_records:
        return None

    if len(messages_records) >= max_retrive_messages:
        logger.error(f"se han recuperado demaciados mensajes que cointienen la subcadena key_word: {key_word}")
        raise ValueError("Se han recuperado demaciados mensajes")

    channels : Dict[int, List] = {}
    for msg in messages_records:
        channel_id = msg.channel_id
        message_create_at = msg.message_create_at
        message_id = msg.id
        message_dict = {"message_create_at":message_create_at, "id":message_id}

        if channel_id not in channels:
            channels[channel_id] = [message_dict]
        else:
            channels[channel_id].append(message_dict)
    
    return channels



def fetch_messages_by_keyword_with_regex(
    session: Session,
    key_word: str,
    max_retrive_messages : int = 300
) -> Dict[int, List[MessagesKeyWord]]:
    """
    Recupera los registros de DiscordMessages cuyo content
    contenga exactamente `key_word`.
    """
    logger.info("=== fetch_messages_by_keyword_with_regex")

    messages_records = (
        session.query(models.DiscordMessage)
        .filter(
            models.DiscordMessage.content.op("~*")(
                rf"\m{key_word}\M"
            )
        )
        .all()
    )
    logger.info(f"Se han recuperado {len(messages_records)} mensajes que cointinene una cadena exata a {key_word}")

    if not messages_records:
        return None
    
    if len(messages_records) >= max_retrive_messages:
        logger.error(f"se han recuperado demaciados mensajes que cointienen exactamente key_word: {key_word}")
        raise ValueError("Se han recuperado demaciados mensajes")

    channels: Dict[int, List] = {}

    for msg in messages_records:
        channel_id = msg.channel_id

        message_dict = {
            "message_create_at": msg.message_create_at,
            "id": msg.id
        }

        if channel_id not in channels:
            channels[channel_id] = [message_dict]
        else:
            channels[channel_id].append(message_dict)

    return channels





class MergeMessages(TypedDict):
    messages_record : List[models.DiscordMessage]
    channel_id : int
    start_time : str
    end_time : str


def merge_message(session : Session, channel_id : int, messages_date : List[datetime], days : int = 4) -> MergeMessages:
    logger.info("=== merge_message")
    if not messages_date:
        return []
    
    # Construir condiciones OR para cada fecha
    conditions = []
    for date in messages_date:
        start_date = date - timedelta(days=days)
        end_date = date + timedelta(days=days)
        conditions.append(
            models.DiscordMessage.message_create_at.between(start_date, end_date)
        )
    
    # Una sola consulta
    messages_record = session.query(models.DiscordMessage).filter(
        models.DiscordMessage.channel_id == channel_id,
        or_(*conditions)
    ).order_by(models.DiscordMessage.message_create_at).all()

    start_time = messages_record[0].message_create_at.strftime("%d/%m/%Y %H:%M")
    end_time = messages_record[-1].message_create_at.strftime("%d/%m/%Y %H:%M")
    
    return {"messages_record":messages_record, "channel_id":channel_id, "start_time":start_time, "end_time":end_time}  





# Función para reemplazar menciones <@ID> por @Nombre
def replace_mentions(text, mapping):
    if not text: return ""
    # Busca el patrón <@números>
    return re.sub(r'<@!?(\d+)>', lambda m: f"@{mapping.get(m.group(1), 'usuario_desconocido')}", text)



def get_format_messages(messages_records : List[models.DiscordMessage]) -> str:
    logger.info("=== get_format_messages")
    
    # Crear un mapa de UserID -> Name y MessageID -> MessageRecord
    # Esto evita consultas repetitivas a la base de datos (N+1)
    user_map = {str(msg.user_id): msg.user_name for msg in messages_records}
    msg_map = {msg.id: msg for msg in messages_records}

    TEMPLATE_1 = "User: {user_name}  | Date: {date}\nContent: {content}\n\n" # (ID: {user_id})
    TEMPLATE_2 = "User: {user_name}  | Date: {date} | Reply to: {reply_to_name}\nContent: {content}\n\n" # (ID: {user_id})

    final_transcript = []

    for obj in messages_records:
        try:
            # Limpiar el contenido reemplazando IDs por nombres
            clean_content = replace_mentions(obj.content, user_map)
            date_str = obj.message_create_at.strftime("%d/%m/%Y %H:%M")
            
            # Lógica de respuesta
            if obj.reply_to:
                # Intentamos buscar el nombre en nuestro mapa local primero
                parent_msg = msg_map.get(obj.reply_to)
                if parent_msg:
                    reply_name = parent_msg.user_name
                else:
                    # Si la respuesta es a un mensaje fuera de este rango de tiempo,
                    # podrías hacer una consulta rápida o poner "mensaje previo"
                    reply_name = "usuario_en_hilo_anterior"
                
                msg_text = TEMPLATE_2.format(
                    user_name=obj.user_name,
                    #user_id=obj.user_id,
                    date=date_str,
                    reply_to_name=reply_name,
                    content=clean_content
                )
            else:
                msg_text = TEMPLATE_1.format(
                    user_name=obj.user_name,
                    #user_id=obj.user_id,
                    date=date_str,
                    content=clean_content
                )
            
            final_transcript.append(msg_text)

        except Exception as e:
            print(f"Error procesando mensaje {obj.id}: {e}")
    
    fianl_messages = "".join(final_transcript)

    return fianl_messages





class MessageChunk(TypedDict):
    channel_name : str
    server_name : str
    start_time : str
    end_time : str
    fianl_messages : str
    channel_id : int

def get_all_messages_chunks(session : Session, key_word : str):
    logger.info("=== get_all_messages_chunks")

    keyword_dict = fetch_messages_by_keyword(session=session, key_word=key_word)
    if keyword_dict is None:
        return None
    
    channels_with_servers = session.query(
        models.DiscordChannel.name.label('channel_name'),
        models.DiscordGuild.name.label('guild_name'),
        models.DiscordChannel.id.label('channel_id')
    ).join(
        models.DiscordGuild,
        models.DiscordGuild.id == models.DiscordChannel.guild_id
    ).all()

    dicord_list = [
        (z, {"channel_name":x, "guild_name":y})
        for x, y, z in channels_with_servers
    ]
    discord_dict = dict(dicord_list)
    #print(discord_dict)
    
    channel_id_keys =  list(keyword_dict.keys())
    response = []
    for channel_id in channel_id_keys:
        print(f"channel_id: {channel_id}")
        messages_date = [d.get("message_create_at") for d in keyword_dict[channel_id]]
        merge_dict = merge_message(session=session, channel_id=channel_id, messages_date=messages_date)
        
        fianl_messages = get_format_messages(messages_records=merge_dict["messages_record"])
        start_time = merge_dict["start_time"]
        end_time = merge_dict["end_time"]
        channel_name = discord_dict[channel_id]["channel_name"]
        server_name = discord_dict[channel_id]["guild_name"]

        message_chunk = {"channel_name":channel_name, "server_name":server_name, "start_time":start_time, "end_time":end_time, "fianl_messages":fianl_messages, "channel_id":channel_id}
        response.append(message_chunk)
    
    # print(response)
    return response






def get_all_messages_chunks_with_regex(session : Session, key_word : str):
    logger.info("=== get_all_messages_chunks")

    keyword_dict = fetch_messages_by_keyword_with_regex(session=session, key_word=key_word)
    if keyword_dict is None:
        return None
    
    channels_with_servers = session.query(
        models.DiscordChannel.name.label('channel_name'),
        models.DiscordGuild.name.label('guild_name'),
        models.DiscordChannel.id.label('channel_id')
    ).join(
        models.DiscordGuild,
        models.DiscordGuild.id == models.DiscordChannel.guild_id
    ).all()

    dicord_list = [
        (z, {"channel_name":x, "guild_name":y})
        for x, y, z in channels_with_servers
    ]
    discord_dict = dict(dicord_list)
    #print(discord_dict)
    
    channel_id_keys =  list(keyword_dict.keys())
    response = []
    for channel_id in channel_id_keys:
        print(f"channel_id: {channel_id}")
        messages_date = [d.get("message_create_at") for d in keyword_dict[channel_id]]
        merge_dict = merge_message(session=session, channel_id=channel_id, messages_date=messages_date)
        
        fianl_messages = get_format_messages(messages_records=merge_dict["messages_record"])
        start_time = merge_dict["start_time"]
        end_time = merge_dict["end_time"]
        channel_name = discord_dict[channel_id]["channel_name"]
        server_name = discord_dict[channel_id]["guild_name"]

        message_chunk = {"channel_name":channel_name, "server_name":server_name, "start_time":start_time, "end_time":end_time, "fianl_messages":fianl_messages, "channel_id":channel_id}
        response.append(message_chunk)
    
    # print(response)
    return response

        
    



if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src import discord_models as models
    from src import settings

    from pathlib import Path
    root_dir = Path(__file__).resolve().parent


    engine = create_engine(settings.DB_DISCORD_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()

    key_word = "Manhattan"
    keyword_dict = fetch_messages_by_keyword(session=session, key_word=key_word)

    # print(f"channel_id keys: {list(keyword_dict.keys())} \n\n")

    # channel_id_keys =  list(keyword_dict.keys())

    # response = []
    # for channel_id in channel_id_keys:
    #     print(f"channel_id: {channel_id}")
    #     messages_date = [d.get("message_create_at") for d in keyword_dict[channel_id]]
    #     merge_dict = merge_message(session=session, channel_id=channel_id, messages_date=messages_date)

    #     channel = session.query(models.DiscordChannel).filter_by(id=channel_id).first()
    #     channel_name = channel.name
    #     server = session.query(models.DiscordGuild).filter_by(id=channel.guild_id).first()
    #     server_name = server.name

    #     fianl_messages = get_format_messages(messages_records=merge_dict["messages_record"])


    #     title = f"## Mensajes del canal de discord: {channel_name} del servidor {server_name} desde {merge_dict.get("start_time")} hasta {merge_dict.get("end_time")}"
    #     r = "\n\n".join([title, fianl_messages, "---"])
    #     response.append(r)
    
    # file = "\n\n\n\n\n\n".join(response)
    
    # path = root_dir / "retrive_by_key_word.md"
    # with open(path, "w", encoding="utf-8") as f:
    #     f.write(file)

    get_all_messages_chunks(session=session, key_word=key_word)









"""
python3 -m src.services.v1.ChatEdubotv2.Edubot.retrive_messages


"""