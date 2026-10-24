import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI application lifespan handler."""
    logger.info(f"Starting {settings.APP_NAME} service in {settings.APP_ENV} mode...")
    from app.core.native import load_in_safe_order
    load_in_safe_order()
    from app.core.live_events import live_events
    from app.tools.system.reminders import reminders_tool, run_reminder_scheduler
    live_events.bind_loop(asyncio.get_running_loop())
    warm_up = asyncio.create_task(_warm_up())
    reminders = asyncio.create_task(run_reminder_scheduler(reminders_tool))
    from app.tools.utilities.briefing import run_briefing_scheduler
    briefing = asyncio.create_task(run_briefing_scheduler())
    from app.tools.utilities.wrap_up import run_wrap_up_scheduler
    wrap_up = asyncio.create_task(run_wrap_up_scheduler())
    from app.tools.productivity.routine_tool import run_routine_scheduler
    routines = asyncio.create_task(run_routine_scheduler())
    from app.services.proactive import run_proactive_loop
    proactive = asyncio.create_task(run_proactive_loop())
    from app.memory.digest import run_digest_loop
    from app.memory.events import MemoryEventType, memory_event_bus
    from app.memory.facts import tidy_old_memories
    for change in (MemoryEventType.MEMORY_CREATED, MemoryEventType.MEMORY_UPDATED, MemoryEventType.MEMORY_DELETED):
        # Settings > Memory refreshes itself when HARIKA learns or forgets something.
        memory_event_bus.subscribe(change, lambda name, payload: live_events.publish("memory", change=name))
    try:
        tidy_old_memories()
    except Exception as exc:
        logger.warning(f"Old memories left as they were: {exc}")
    digests = asyncio.create_task(run_digest_loop())
    from app.tools.system.screen_reader import foreground_tracker
    foreground_tracker.start()  # remembers the app you were in before talking to HARIKA
    from app.voice.engine import voice_engine
    voice_engine.on_request = _voice_request
    voice_engine.start(asyncio.get_running_loop())  # only if "Hey HARIKA" is turned on
    yield
    warm_up.cancel()
    reminders.cancel()
    briefing.cancel()
    wrap_up.cancel()
    routines.cancel()
    proactive.cancel()
    digests.cancel()
    foreground_tracker.stop()
    await asyncio.to_thread(voice_engine.stop)
    logger.info(f"Shutting down {settings.APP_NAME} service gracefully...")


async def _voice_request(text: str) -> dict:
    """A spoken request goes through the same router (and conversation) as typing."""
    from app.router.manager import router_manager
    from app.voice.engine import voice_engine

    user = voice_engine.settings.load()["user_name"] or "default"
    result = await router_manager.route_request(text, user_id=user, spoken=True)
    return {"text": result.get("response", ""), "tone": result.get("tone") or "warm"}


async def _warm_up():
    """Index installed apps and load the local model in the background so first requests are fast."""
    from app.cognition.core import cognitive_core
    from app.cognition.llm.manager import RoleProvider, usable_model
    from app.tools.system.installed_apps import installed_app_index

    async def check_conversation_model():
        # Learns which models the conversation service offers now, so the first reply doesn't wait for it.
        first = RoleProvider("conversation").chain()[0]
        await usable_model(first["service"], "conversation")

    def prepare_meaning_model():
        # Fetched once (about 23 MB); until then requests are matched to abilities by their words.
        from app.cognition.semantic.embedder import embedder
        if embedder.download():
            embedder.embed(["hello"])  # load it now rather than on the first request

    # Side by side: the first request shouldn't wait for app indexing to finish.
    results = await asyncio.gather(asyncio.to_thread(installed_app_index.apps), cognitive_core.warm_up(),
                                   check_conversation_model(), asyncio.to_thread(prepare_meaning_model),
                                   return_exceptions=True)
    for result in results:
        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
            logger.warning(f"Background warm-up step skipped: {result}")


app = FastAPI(
    title=settings.APP_NAME,
    description="HARIKA AI Operating System Orchestration & Engine API",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Origins of the packaged desktop app's webview (Windows/Linux and macOS), allowed
# regardless of .env so the installed app can always reach its own backend.
DESKTOP_APP_ORIGINS = ["http://tauri.localhost", "https://tauri.localhost", "tauri://localhost"]

# CORS middleware configuration
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys([*settings.CORS_ORIGINS, *DESKTOP_APP_ORIGINS])),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root status endpoint."""
    return {
        "system": settings.APP_NAME,
        "status": "online",
        "version": "0.1.0",
        "docs_url": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
