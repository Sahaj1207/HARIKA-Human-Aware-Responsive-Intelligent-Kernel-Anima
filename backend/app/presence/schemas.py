from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AttentionLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    HIGHEST = "HIGHEST"


class EntityItem(BaseModel):
    entity: str
    attribute: str
    value: Any
    confidence: float = 1.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkspaceItem(BaseModel):
    key: str  # project, file, bug, code, image, discussion, plan
    value: Any
    created_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    ttl_seconds: float = 600.0  # 10 minute default expiration


class AttentionState(BaseModel):
    level: AttentionLevel = AttentionLevel.LOW
    focus_topic: Optional[str] = None
    active_trigger: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GoalInference(BaseModel):
    inferred_goal: str
    confidence: float
    suggestion: Optional[str] = None
    reason: str


class ReflectionResult(BaseModel):
    retrieved_correct_memory: bool = True
    executed_correct_tool: bool = True
    answered_user_question: bool = True
    reason: str = "Reasoning validated."


class VerificationResult(BaseModel):
    memory_verified: bool = True
    tool_verified: bool = True
    vision_verified: bool = True
    planning_verified: bool = True
    agent_verified: bool = True
    overall_valid: bool = True


class ContradictionResult(BaseModel):
    has_contradiction: bool = False
    archived_memory_id: Optional[str] = None
    updated_memory_id: Optional[str] = None
    revision: int = 1


class ExperienceDecision(BaseModel):
    decision: str = "proceed"  # proceed, suggest_break, offer_diagnostics, offer_rehearsal
    reason: str = "Standard user experience."
    tone_modifier: Optional[str] = None


class ConversationState(BaseModel):
    current_topic: Optional[str] = None
    current_goal: Optional[str] = None
    current_task: Optional[str] = None
    current_project: Optional[str] = None
    conversation_mode: str = "active"
    recent_entities: List[EntityItem] = Field(default_factory=list)
    recent_corrections: List[Dict[str, Any]] = Field(default_factory=list)
    recent_failures: List[str] = Field(default_factory=list)
    recent_successes: List[str] = Field(default_factory=list)


class PresenceScore(BaseModel):
    awareness: float = 100.0
    continuity: float = 100.0
    verification: float = 100.0
    initiative_quality: float = 100.0
    correction_recovery: float = 100.0
    memory_quality: float = 100.0
    attention_stability: float = 100.0
    overall_score: float = 100.0


class PresenceResult(BaseModel):
    presence_id: str
    natural_response: str
    structured_output: Dict[str, Any]
    verified: bool = True
    attention: AttentionLevel = AttentionLevel.MEDIUM
    latency_ms: float = 0.0


class PresenceMetrics(BaseModel):
    total_observations: int = 0
    initiatives_offered: int = 0
    reflections_passed: int = 0
    verifications_passed: int = 0
    corrections_repaired: int = 0
    average_presence_latency_ms: float = 0.0
