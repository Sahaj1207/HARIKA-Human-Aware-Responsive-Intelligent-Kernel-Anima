from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.router.manager import router_manager
from app.router.history import router_history_manager
from app.router.metrics import router_metrics_manager
from app.router.schemas import RouterMetrics, SimulationRequest, SimulationResponse

router = APIRouter()


class RouteRequestPayload(BaseModel):
    message: str = Field(..., example="Calculate 25 * 18")
    user_id: str = Field(default="default")
    session_id: str = Field(default="default")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(default=None)


@router.get("", response_model=Dict[str, Any])
async def get_router_status():
    """Returns HARIKA Cognitive Router status and metrics summary."""
    m = router_metrics_manager.get_metrics()
    return {
        "status": "healthy",
        "engine": "Cognitive Router v1.0",
        "total_requests": m.total_requests,
        "average_routing_latency_ms": m.average_routing_latency_ms,
        "routing_accuracy": m.routing_accuracy
    }


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_router_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns persistent decision trace log."""
    return router_history_manager.get_history(limit=limit)


@router.get("/metrics", response_model=RouterMetrics)
async def get_router_metrics():
    """Returns self-learning telemetry metrics for the Cognitive Router."""
    return router_metrics_manager.get_metrics()


@router.post("/decision", response_model=Dict[str, Any])
@router.post("/route", response_model=Dict[str, Any])
async def route_user_request(payload: RouteRequestPayload):
    """Processes user directive through the full Cognitive Router pipeline."""
    try:
        return await router_manager.route_request(
            message=payload.message,
            user_id=payload.user_id,
            session_id=payload.session_id,
            conversation_history=payload.conversation_history
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulate", response_model=SimulationResponse)
async def simulate_user_request(payload: SimulationRequest):
    """Dry run mode predicting intent, confidence, policy, and engine without side-effects."""
    try:
        return router_manager.simulate_request(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
