from fastapi import APIRouter
from app.api.v1.endpoints import health, chat, events, llm_settings, speech, daily, accounts, proactive, privacy, memory, tools, planning, vision, agents, voice, router as router_ep, presence as presence_ep

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, tags=["Cognition Chat"])
api_router.include_router(events.router, tags=["Live Events"])
api_router.include_router(llm_settings.router, prefix="/settings/llm", tags=["Settings: Brain"])
api_router.include_router(speech.router, prefix="/speech", tags=["Voice"])
api_router.include_router(daily.router, prefix="/settings/daily", tags=["Settings: Daily"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["Settings: Accounts"])
api_router.include_router(proactive.router, prefix="/settings/proactive", tags=["Settings: Heads-up"])
api_router.include_router(privacy.router, prefix="/settings/privacy", tags=["Settings: Privacy"])
api_router.include_router(memory.router, prefix="/memory", tags=["Cognitive Memory"])
api_router.include_router(tools.router, prefix="/tools", tags=["Action Engine Tools"])
api_router.include_router(planning.router, prefix="/planning", tags=["Reflection & Planning Engine"])
api_router.include_router(vision.router, prefix="/vision", tags=["Multimodal Vision Engine"])
api_router.include_router(agents.router, prefix="/agents", tags=["Autonomous Agent Engine"])
api_router.include_router(voice.router, prefix="/voice", tags=["Voice Engine 2.0"])
api_router.include_router(router_ep.router, prefix="/router", tags=["Cognitive Router v1.0"])
api_router.include_router(presence_ep.router, prefix="/presence", tags=["Presence Engine v1.1"])





