
from sqlalchemy import Column, Integer, BigInteger, String, JSON, DateTime, func, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy import Enum
import enum



class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "discord_users"

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(BigInteger, nullable=False)
    discord_name = Column(String, nullable=False)
    inserted_at = Column(DateTime, server_default=func.now())


class UserChat(Base):
    __tablename__ = "users_chats"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("discord_users.id"))
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
    user_id = Column(Integer, ForeignKey("discord_users.id"))
    role = Column(Enum(MessageRole), nullable=False)
    message = Column(JSON)
    create_at = Column(DateTime, server_default=func.now())


