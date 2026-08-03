from fastapi import APIRouter
from app.api.v1.endpoints import health, chat, memory

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, tags=["Cognition Chat"])
api_router.include_router(memory.router, prefix="/memory", tags=["Cognitive Memory"])
