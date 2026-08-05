from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AgentState(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentContext(BaseModel):
    user_id: str = "default"
    goal_id: Optional[str] = None
    plan_id: Optional[str] = None
    current_step_index: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentTaskResult(BaseModel):
    task_id: str
    step_number: int = 1
    title: str = ""
    tool_name: Optional[str] = None
    success: bool = True
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    retry_count: int = 0


class AgentStatus(BaseModel):
    agent_id: str
    goal_id: Optional[str] = None
    plan_id: Optional[str] = None
    state: AgentState = AgentState.CREATED
    current_task: Optional[str] = None
    progress_percent: float = 0.0
    running_duration_s: float = 0.0
    retries_count: int = 0
    completed_tasks_count: int = 0
    total_tasks_count: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentHistoryItem(BaseModel):
    agent_id: str
    goal_id: Optional[str] = None
    plan_id: Optional[str] = None
    tasks_count: int = 0
    duration_ms: float = 0.0
    result_summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentMetrics(BaseModel):
    agents_created: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    average_duration_s: float = 0.0
    retry_rate_percent: float = 0.0
    success_rate_percent: float = 100.0
    average_tasks_per_agent: float = 0.0


class StartAgentPayload(BaseModel):
    user_message: str = Field(..., example="Create a React application")
    goal_id: Optional[str] = None
    priority: str = Field(default="NORMAL")
