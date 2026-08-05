from fastapi import APIRouter
from app.api.v1.endpoints import health, chat, memory, tools, planning, vision, agents

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, tags=["Cognition Chat"])
api_router.include_router(memory.router, prefix="/memory", tags=["Cognitive Memory"])
api_router.include_router(tools.router, prefix="/tools", tags=["Action Engine Tools"])
api_router.include_router(planning.router, prefix="/planning", tags=["Reflection & Planning Engine"])
api_router.include_router(vision.router, prefix="/vision", tags=["Multimodal Vision Engine"])
api_router.include_router(agents.router, prefix="/agents", tags=["Autonomous Agent Engine"])


