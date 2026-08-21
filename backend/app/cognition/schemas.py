from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.router.action_graph import ActionGraph
    from app.router.schemas import RequestContext


class CognitiveMode(str, Enum):
    ANSWER = "ANSWER"
    ACT = "ACT"
    ASK = "ASK"
    PLAN = "PLAN"
    REMEMBER = "REMEMBER"
    WAIT = "WAIT"
    REPORT_UNSUPPORTED = "REPORT_UNSUPPORTED"


class CognitiveGoal(BaseModel):
    probable_goal: str
    desired_outcome: str
    confidence: float
    entities: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)


class CognitiveDecision(BaseModel):
    request: str
    context: Any
    goal: CognitiveGoal
    mode: CognitiveMode
    confidence: float
    action_graph: Any
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    rationale: str = ""
    semantic_request: Optional[Any] = None
