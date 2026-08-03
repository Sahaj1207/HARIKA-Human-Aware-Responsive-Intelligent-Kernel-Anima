from datetime import datetime, timezone
from fastapi import APIRouter
from app.schemas.health import HealthResponse, SystemMetrics
from app.core.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Returns the operational status of the HARIKA backend service."""
    return HealthResponse(
        status="online",
        app_name=settings.APP_NAME,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/metrics", response_model=SystemMetrics)
async def get_metrics():
    """Returns system operational metrics placeholder."""
    return SystemMetrics(
        status="nominal",
        cpu_usage_percent=12.4,
        memory_usage_percent=38.2,
        active_services=4
    )
