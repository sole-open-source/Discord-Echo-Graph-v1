
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, List, Optional, Union

from langchain_groq import ChatGroq
from src import settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src import chatedubot_models as models

from src.services.v1.ChatEdubot.run_chat import run_chat

from src.logging_config import get_logger
logger = get_logger(module_name="run_chat_api", DIR="apiv2")


router = APIRouter(prefix="/educhat")

engine = create_engine(settings.DB_EDUCHAT_CONN_STRING)
MySession = sessionmaker(bind=engine)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.3,
    api_key=settings.GROQ_API_KEY
)


# ==============================================
# ==============================================

class CreateUser(BaseModel):
    discord_name: str


class CreateUserResponse(BaseModel):
    user_id: int


@router.post("/newuser", response_model=CreateUserResponse)
def create_user_api(body: CreateUser):
    session = MySession()
    try:
        user_record = models.User(
            discord_user_id=1234567890,
            discord_name=body.discord_name
        )
        session.add(user_record)
        session.commit()
        session.refresh(user_record)
        return {"user_id": user_record.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"error: {e}")
    finally:
        session.close()


# ==============================================
# ==============================================

class CreateChat(BaseModel):
    user_id: int


class CreateChatResponse(BaseModel):
    chat_id: int


@router.post("/newchat", response_model=CreateChatResponse)
def create_chat_api(body: CreateChat):
    session = MySession()
    try:
        chat_record = models.UserChat(user_id=body.user_id)
        session.add(chat_record)
        session.commit()
        session.refresh(chat_record)
        return {"chat_id": chat_record.id}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"error: {e}")
    finally:
        session.close()


# ==============================================
# ==============================================

class ToolCallSchema(BaseModel):
    name: str
    args: dict
    id: str
    type: str


class AiMessageResponse(BaseModel):
    type: str
    content: Any
    tool_calls: List[ToolCallSchema]
    usage_metadata: Optional[dict]


class ToolMessageResponse(BaseModel):
    type: str
    content: Any
    tool_call_id: str
    name: Optional[str]


class RunChat(BaseModel):
    user_id: int
    chat_id: int
    human_message: str


class RunChatResponse(BaseModel):
    messages: List[Union[AiMessageResponse, ToolMessageResponse]]


@router.post("/run", response_model=RunChatResponse)
def run_chat_api(body: RunChat):
    try:
        response = run_chat(
            user_id=body.user_id,
            chat_id=body.chat_id,
            human_message=body.human_message,
            llm=llm
        )
        return {"messages": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error: {e}")
