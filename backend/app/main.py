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
    from app.core.live_events import live_events
    from app.tools.system.reminders import reminders_tool, run_reminder_scheduler
    live_events.bind_loop(asyncio.get_running_loop())
    warm_up = asyncio.create_task(_warm_up())
    reminders = asyncio.create_task(run_reminder_scheduler(reminders_tool))
    from app.tools.utilities.briefing import run_briefing_scheduler
    briefing = asyncio.create_task(run_briefing_scheduler())
    from app.tools.productivity.routine_tool import run_routine_scheduler
    routines = asyncio.create_task(run_routine_scheduler())
    from app.services.proactive import run_proactive_loop
    proactive = asyncio.create_task(run_proactive_loop())
    from app.memory.digest import run_digest_loop
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
    try:
        from app.tools.system.installed_apps import installed_app_index
        await asyncio.to_thread(installed_app_index.apps)
        from app.cognition.core import cognitive_core
        await cognitive_core.warm_up()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(f"Background warm-up skipped: {exc}")


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
