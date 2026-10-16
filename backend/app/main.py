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
    warm_up = asyncio.create_task(_warm_up())
    yield
    warm_up.cancel()
    logger.info(f"Shutting down {settings.APP_NAME} service gracefully...")


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

# CORS middleware configuration
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
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
