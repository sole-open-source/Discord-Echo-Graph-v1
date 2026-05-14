import asyncio
import discord
from discord.ext import commands
from langchain_groq import ChatGroq
from pathlib import Path
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import settings
from src import chatedubot_models as model
from .run_chat import run_chat
from .Edubot.graph import create_chat_edubot
from .Edubot.prompts import EDUBOT_SYSTEM_PROMPT_1
from .OriginabotdbAgent.graph import create_chat_agent
from .OriginabotdbAgent.prompts import DB_AGENT_SYSTEM_PROMPT_3
from src.logging_config import get_logger

logger = get_logger(module_name="botv3", DIR="botv3")


# ================================================================
# LLM
# ================================================================

LLM = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.3,
    api_key=settings.GROQ_API_KEY,
)


# ================================================================
# Engines y session factories
# ================================================================

_educhat_engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
_EduchatSession = sessionmaker(bind=_educhat_engine)

_discord_engine = create_engine(settings.DB_DISCORD_CONN_STRING)
_DiscordSession = sessionmaker(bind=_discord_engine)

_originabotdb_engine = create_engine(
    f"postgresql+psycopg2://{settings.DB_USER}:postgres"
    f"@localhost:5432/originabotdb"
)

# Sesiones long-lived compartidas por los agentes para escribir UsageMetadata
# y para las búsquedas en Discord. Se crean una vez al inicio del bot.
_agent_educhat_session = _EduchatSession()
_discord_session = _DiscordSession()


# ================================================================
# Compilación de agentes (una sola vez al arranque)
# ================================================================

_root_dir = Path(__file__).resolve().parent

with open(_root_dir / "OriginabotdbAgent" / "originabotSKILL.md", encoding="utf-8") as _f:
    _originabot_description = _f.read()

with open(_root_dir / "OriginabotdbAgent" / "originabot.json", encoding="utf-8") as _f:
    _originabotdb_json = json.load(_f)

_semaphore = asyncio.Semaphore(3)

_originabotdb_subagent = create_chat_agent(
    llm=LLM,
    engine=_originabotdb_engine,
    originabotdb_json=_originabotdb_json,
    educhat_session=_agent_educhat_session,
)

_chat_agent = create_chat_edubot(
    llm=LLM,
    originabotdb_subagent=_originabotdb_subagent,
    session=_discord_session,
    educhat_session=_agent_educhat_session,
    semaphore=_semaphore,
)

_EDUBOT_SYSTEM_MESSAGE = EDUBOT_SYSTEM_PROMPT_1
_ORIGINABOT_SYSTEM_MESSAGE = DB_AGENT_SYSTEM_PROMPT_3.format(
    top_n=15,
    description=_originabot_description,
)

logger.info("Agentes compilados y listos")


# ================================================================
# Estado en memoria del bot
# ================================================================

# discord_user_id -> {user_db_id, chat_id, channel_id}
_active_chats: dict[int, dict] = {}

# Lock por usuario para serializar mensajes concurrentes del mismo usuario
_user_locks: dict[int, asyncio.Lock] = {}


# ================================================================
# Helpers de DB
# ================================================================

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


# ================================================================
# Helpers de formato
# ================================================================

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


# ================================================================
# Bot de Discord
# ================================================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def _is_allowed():
    async def predicate(ctx: commands.Context) -> bool:
        if settings.ALLOWED_DISCORD_USER_IDS and ctx.author.id not in settings.ALLOWED_DISCORD_USER_IDS:
            await ctx.reply("No tienes permiso para usar este bot.")
            return False
        return True
    return commands.check(predicate)


@bot.event
async def on_ready():
    logger.info(f"Bot v3 conectado como {bot.user} (id: {bot.user.id})")


@bot.command(name="chat")
@_is_allowed()
async def start_chat(ctx: commands.Context):
    """Inicia una sesión de chat con el agente. Uso: !chat"""
    if ctx.author.id in _active_chats:
        await ctx.reply("Ya tienes una sesión activa. Escribe `!end` para terminarla antes de iniciar una nueva.")
        return

    session = _EduchatSession()
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

    if settings.ALLOWED_DISCORD_USER_IDS and message.author.id not in settings.ALLOWED_DISCORD_USER_IDS:
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

    lock = _user_locks.setdefault(message.author.id, asyncio.Lock())
    async with lock:
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
                            session=_EduchatSession(),
                            user_id=user_db_id,
                            chat_id=chat_id,
                            human_message=human_message,
                            chat_agent=_chat_agent,
                            edubot_system_message=_EDUBOT_SYSTEM_MESSAGE,
                            originabot_system_message=_ORIGINABOT_SYSTEM_MESSAGE,
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
    bot.run(settings.DULCINEA_DISCORD_BOT_TOKEN)


"""
python3 -m src.services.v1.ChatEdubotv3.main


"""
