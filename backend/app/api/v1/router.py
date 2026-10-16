from fastapi import APIRouter
from app.api.v1.endpoints import health, chat, events, memory, tools, planning, vision, agents, voice, router as router_ep, presence as presence_ep

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, tags=["Cognition Chat"])
api_router.include_router(events.router, tags=["Live Events"])
api_router.include_router(memory.router, prefix="/memory", tags=["Cognitive Memory"])
api_router.include_router(tools.router, prefix="/tools", tags=["Action Engine Tools"])
api_router.include_router(planning.router, prefix="/planning", tags=["Reflection & Planning Engine"])
api_router.include_router(vision.router, prefix="/vision", tags=["Multimodal Vision Engine"])
api_router.include_router(agents.router, prefix="/agents", tags=["Autonomous Agent Engine"])
api_router.include_router(voice.router, prefix="/voice", tags=["Voice Engine 2.0"])
api_router.include_router(router_ep.router, prefix="/router", tags=["Cognitive Router v1.0"])
api_router.include_router(presence_ep.router, prefix="/presence", tags=["Presence Engine v1.1"])





