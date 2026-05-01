from fastapi import FastAPI
from src.api.v1.routers import fetchDiscordApi, chatEdubotApi

app = FastAPI(title="Discord-Echo_Saver", lifespan=fetchDiscordApi.lifespan)
app.include_router(fetchDiscordApi.router)
app.include_router(chatEdubotApi.router)



"""
uvicorn src.api.main:app --reload


"""
