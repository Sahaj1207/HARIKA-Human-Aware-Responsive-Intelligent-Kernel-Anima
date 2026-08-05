from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class PlanState(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GoalPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


class GoalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class DecisionStrategy(str, Enum):
    RESPOND_NORMALLY = "RESPOND_NORMALLY"
    RETRIEVE_MEMORY = "RETRIEVE_MEMORY"
    EXECUTE_TOOL = "EXECUTE_TOOL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    REJECT_REQUEST = "REJECT_REQUEST"


class Task(BaseModel):
    id: str = Field(..., description="Unique task identifier")
    goal_id: str = Field(..., description="Parent goal identifier")
    title: str = Field(..., description="Short task title")
    status: str = Field(default="pending", description="Task status ('pending', 'in_progress', 'completed', 'failed')")
    priority: GoalPriority = Field(default=GoalPriority.NORMAL)
    depends_on: List[str] = Field(default_factory=list, description="Task IDs this task depends on")
    estimated_duration_ms: float = 1000.0
    tool_required: Optional[str] = None
    completed: bool = False


class Goal(BaseModel):
    id: str = Field(..., description="Unique goal identifier")
    title: str = Field(..., description="Short goal title")
    description: str = Field(default="", description="Detailed goal description")
    priority: GoalPriority = Field(default=GoalPriority.NORMAL)
    status: GoalStatus = Field(default=GoalStatus.ACTIVE)
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PlanStep(BaseModel):
    step_number: int
    title: str
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class Plan(BaseModel):
    id: str = Field(..., description="Unique plan identifier")
    goal_id: Optional[str] = None
    state: PlanState = Field(default=PlanState.CREATED)
    steps: List[PlanStep] = Field(default_factory=list)
    version: int = 1
    revision: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Decision(BaseModel):
    strategy: DecisionStrategy = Field(default=DecisionStrategy.RESPOND_NORMALLY)
    reason: str = Field(default="Default response strategy selected.")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    selected_tool: Optional[str] = None


class Reflection(BaseModel):
    id: str = Field(..., description="Unique reflection identifier")
    summary: str = Field(..., description="High-level summary of what happened")
    outcome: str = Field(..., description="Outcome description")
    success: bool = True
    confidence: float = 0.9
    was_tool_used: bool = False
    lessons_learned: str = "Nominal interaction."
    next_recommendation: str = "Continue active context."
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ValidationReport(BaseModel):
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PlanningMetrics(BaseModel):
    total_plans: int
    executed_plans: int
    success_rate: float
    average_planning_latency_ms: float
    clarification_rate: float
    tool_usage_rate: float
