import asyncio
import discord
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq


from src import settings
from src import chatedubot_models as model
from .run_chat import run_chat
from src.logging_config import get_logger

logger = get_logger(module_name="botv2", DIR="botv2")

# LLM = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     temperature=0.5,
#     api_key=settings.GOOGLE_API_KEY,
# )
LLM = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.3,
    api_key=settings.GROQ_API_KEY
)

# discord_user_id -> {user_db_id, chat_id, channel_id}
_active_chats: dict[int, dict] = {}


def _get_or_create_user(session, discord_user_id: int, discord_name: str) -> int:
    user = session.query(model.User).filter_by(discord_user_id=discord_user_id).first()
    if user is None:
        user = model.User(discord_user_id=discord_user_id, discord_name=discord_name)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user.id


def _create_chat(session, user_db_id: int) -> int:
    chat = model.UserChat(user_id=user_db_id)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat.id


def _split_message(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return str(content)


def _format_response(chat_response: list) -> str:
    ai_content = ""
    tool_names: list[str] = []

    for msg in chat_response:
        msg_type = msg.get("type")
        if msg_type == "Ai":
            text = _extract_text(msg.get("content", ""))
            if text:
                ai_content = text
        elif msg_type == "Tool":
            name = msg.get("name")
            if name:
                tool_names.append(name)

    result = ai_content or "Sin respuesta."
    if tool_names:
        tools_str = ", ".join(f"`{t}`" for t in dict.fromkeys(tool_names))
        result += f"\n\n_Herramientas usadas: {tools_str}_"

    return result


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def _is_allowed():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id not in settings.ALLOWED_DISCORD_USER_IDS:
            await ctx.reply("No tienes permiso para usar este bot.")
            return False
        return True
    return commands.check(predicate)


@bot.event
async def on_ready():
    logger.info(f"Bot v2 conectado como {bot.user} (id: {bot.user.id})")


@bot.command(name="chat")
@_is_allowed()
async def start_chat(ctx: commands.Context):
    """Inicia una sesión de chat con el agente. Uso: !chat"""
    if ctx.author.id in _active_chats:
        await ctx.reply("Ya tienes una sesión activa. Escribe `!end` para terminarla antes de iniciar una nueva.")
        return

    engine = create_engine(settings.CHAT_DB_APP_CONN_STRING)
    MySession = sessionmaker(bind=engine)
    session = MySession()
    try:
        user_db_id = _get_or_create_user(session, ctx.author.id, str(ctx.author))
        chat_id = _create_chat(session, user_db_id)
    finally:
        session.close()

    _active_chats[ctx.author.id] = {
        "user_db_id": user_db_id,
        "chat_id": chat_id,
        "channel_id": ctx.channel.id,
    }
    logger.info(f"Chat iniciado: discord_user={ctx.author} user_db_id={user_db_id} chat_id={chat_id}")
    await ctx.reply("Sesión de chat iniciada. Escríbeme lo que quieras. Usa `!end` para terminar.")


@bot.command(name="end")
@_is_allowed()
async def end_chat(ctx: commands.Context):
    """Termina la sesión de chat activa. Uso: !end"""
    if ctx.author.id not in _active_chats:
        await ctx.reply("No tienes ninguna sesión de chat activa.")
        return

    del _active_chats[ctx.author.id]
    logger.info(f"Chat terminado: discord_user={ctx.author}")
    await ctx.reply("Sesión de chat terminada.")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.content.startswith(bot.command_prefix):
        return

    if message.author.id not in settings.ALLOWED_DISCORD_USER_IDS:
        return

    session_info = _active_chats.get(message.author.id)
    if session_info is None or session_info["channel_id"] != message.channel.id:
        return

    human_message = message.content.strip()
    if not human_message:
        return

    user_db_id = session_info["user_db_id"]
    chat_id = session_info["chat_id"]
    logger.info(f"Mensaje de {message.author} (chat_id={chat_id}): {human_message}")

    async with message.channel.typing():
        max_retries = 3
        wait_seconds = 10
        chat_response = None
        for attempt in range(1, max_retries + 1):
            try:
                loop = asyncio.get_event_loop()
                chat_response = await loop.run_in_executor(
                    None,
                    lambda: run_chat(
                        user_id=user_db_id,
                        chat_id=chat_id,
                        human_message=human_message,
                        llm=LLM,
                    ),
                )
                break
            except Exception as e:
                is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if is_rate_limit and attempt < max_retries:
                    logger.warning(f"Rate limit (intento {attempt}/{max_retries}), reintentando en {wait_seconds}s...")
                    await asyncio.sleep(wait_seconds)
                    wait_seconds *= 2
                else:
                    logger.error(f"Error en run_chat (intento {attempt}): {e}")
                    msg = (
                        "El servicio de IA está temporalmente saturado. Intenta en unos segundos."
                        if is_rate_limit
                        else "Ocurrió un error al procesar tu mensaje. Intenta de nuevo."
                    )
                    await message.reply(msg)
                    return

    reply = _format_response(chat_response)
    for chunk in _split_message(reply):
        await message.reply(chunk)


if __name__ == "__main__":
    bot.run(settings.DISCORD_BOT_TOKEN)


"""

python3 -m src.services.v2.botv2


 Comandos:
  - !chat — activa la sesión de chatbot para ese usuario en ese canal. Crea o recupera el usuario en la DB chat_edubot, crea un nuevo UserChat, y guarda el chat_id en memoria.         
  - !end — termina la sesión activa.                                                                                                                                                    
                                                                                                                                                                                        
  Flujo de mensajes:                                                                                                                                                                    
  - Cualquier mensaje que no empiece con ! de un usuario con sesión activa (en el mismo canal donde escribió !chat) se pasa a run_chat.                                                 
  - run_chat es síncrono, así que se ejecuta en run_in_executor para no bloquear el loop de Discord.                                                                                    
  - La respuesta muestra el contenido del último Ai_Message y, si hubo tool calls, une al pie _Herramientas usadas: \query_lightrag`_`.                                                 
                     


"""