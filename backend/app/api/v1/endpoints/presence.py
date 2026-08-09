from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.presence.manager import presence_manager
from app.presence.schemas import PresenceMetrics

router = APIRouter()


class PresenceProcessPayload(BaseModel):
    intent: str = Field(..., example="TOOL_EXECUTION")
    engine_name: str = Field(..., example="ToolManager")
    raw_message: str = Field(..., example="Open GitHub")
    user_id: str = Field(default="default")


@router.get("/status", response_model=Dict[str, Any])
async def get_presence_status():
    """Returns HARIKA Presence Engine status summary."""
    score = presence_manager.get_presence_score()
    return {
        "status": "online",
        "engine": "HARIKA Presence Engine v1.1",
        "overall_score": score.get("overall_score", 100.0),
        "loop_running": presence_manager.loop.is_running
    }


@router.get("/state", response_model=Dict[str, Any])
async def get_presence_state():
    """Returns HARIKA ongoing awareness state."""
    state = presence_manager.get_state()
    return state.model_dump()


@router.get("/working_memory", response_model=Dict[str, Any])
async def get_working_memory():
    """Returns short-term working memory workspace."""
    return presence_manager.get_working_memory()


@router.get("/score", response_model=Dict[str, Any])
async def get_presence_score():
    """Returns internal health metrics (Developer Diagnostics)."""
    return presence_manager.get_presence_score()


@router.get("/metrics", response_model=PresenceMetrics)
async def get_presence_metrics():
    """Returns telemetry metrics for Presence Engine."""
    from app.presence.metrics import presence_metrics_manager
    return presence_metrics_manager.get_metrics()
