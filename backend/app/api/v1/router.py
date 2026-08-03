from fastapi import APIRouter
from app.api.v1.endpoints import health, chat

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, tags=["Cognition Chat"])
