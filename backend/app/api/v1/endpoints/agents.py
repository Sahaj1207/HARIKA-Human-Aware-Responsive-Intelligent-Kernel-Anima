from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.agents.manager import agent_manager
from app.agents.history import agent_history_manager
from app.agents.metrics import agent_metrics_manager
from app.agents.schemas import AgentStatus, AgentMetrics, StartAgentPayload

router = APIRouter()


class AgentActionPayload(BaseModel):
    agent_id: str = Field(..., example="agent-12345678")


@router.get("", response_model=List[AgentStatus])
async def list_active_agents():
    """Returns all active agent instances and their current lifecycle statuses."""
    return agent_manager.list_active_agents()


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_agent_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns persistent agent execution history log."""
    return agent_history_manager.get_history(limit=limit)


@router.get("/metrics", response_model=AgentMetrics)
async def get_agent_metrics():
    """Returns Agent Engine analytics, success rates, and average durations."""
    return agent_metrics_manager.get_metrics()


@router.post("/start", response_model=Dict[str, Any])
async def start_agent_goal(payload: StartAgentPayload):
    """Creates and starts an autonomous agent executing a multi-step goal."""
    try:
        return await agent_manager.execute_agent_goal(
            user_message=payload.user_message,
            goal_id=payload.goal_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pause", response_model=AgentStatus)
async def pause_agent(payload: AgentActionPayload):
    """Pauses a running agent."""
    try:
        return agent_manager.pause_agent(payload.agent_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume", response_model=AgentStatus)
async def resume_agent(payload: AgentActionPayload):
    """Resumes a paused agent."""
    try:
        return agent_manager.resume_agent(payload.agent_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel", response_model=AgentStatus)
async def cancel_agent(payload: AgentActionPayload):
    """Cleanly cancels an active agent."""
    try:
        return agent_manager.cancel_agent(payload.agent_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
