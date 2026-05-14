
from sqlalchemy import Column, Integer, BigInteger, String, JSON, DateTime, func, ForeignKey, Text, Float
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy import Enum
import enum



class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(BigInteger, nullable=False)
    discord_name = Column(String, nullable=False)
    inserted_at = Column(DateTime, server_default=func.now())


class UserChat(Base):
    __tablename__ = "users_chats"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    create_at = Column(DateTime, server_default=func.now())




class MessageRole(enum.Enum):
    SYSTEM = "System"
    HUMAN = "Human"
    AI = "Ai"
    TOOL = "Tool"


class ChatMessages(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("users_chats.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(Enum(MessageRole), nullable=False)
    message = Column(JSON)
    create_at = Column(DateTime, server_default=func.now())
    # agent_name = Column(String, nullable=True)




class EduBotStates(Base):
    __tablename__ = "edubot_states"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("users_chats.id"))
    sub_chat_id = Column(Integer, nullable=True)
    state = Column(JSON)
    state_name = Column(String, nullable=True)





class ModelsProvider(Base):
    __tablename__ = "models_provider"

    id = Column(Integer, primary_key=True)
    model_name = Column(String, unique=True)
    model_provider = Column(String)
    pricing_input_tokens = Column(Float)
    pricing_output_tokens = Column(Float)
    create_at = Column(DateTime, server_default=func.now())


class MetaDataTask(enum.Enum):
    EDUBOT = "edubot_agent"
    ORIGINABOTDB = "originabotdb_agent"
    LIGHTRAG = "lightrag"
    SEARCH_BY_KEYWORD = "search_by_keyword"



class UsageMetadata(Base):
    __tablename__ = "usage_metadata"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    model_name = Column(String, ForeignKey("models_provider.model_name"))
    task = Column(Enum(MetaDataTask), nullable=True)
    create_at = Column(DateTime, server_default=func.now())


  


