from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class IntentType(str, Enum):
    GREETING = "GREETING"
    SOCIAL_CONVERSATION = "SOCIAL_CONVERSATION"
    CAPABILITY_QUERY = "CAPABILITY_QUERY"
    EXECUTION_FEEDBACK = "EXECUTION_FEEDBACK"

    CHAT = "CHAT"
    MEMORY_STORE = "MEMORY_STORE"
    MEMORY_QUERY = "MEMORY_QUERY"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    VISION_ANALYSIS = "VISION_ANALYSIS"
    PLAN_CREATION = "PLAN_CREATION"
    PLAN_QUERY = "PLAN_QUERY"
    AGENT_START = "AGENT_START"
    AGENT_STATUS = "AGENT_STATUS"
    AGENT_CONTINUE = "AGENT_CONTINUE"
    VOICE_COMMAND = "VOICE_COMMAND"
    SYSTEM_COMMAND = "SYSTEM_COMMAND"
    UNKNOWN_INTENT = "UNKNOWN_INTENT"
    UNKNOWN = "UNKNOWN"






class EnginePriority(int, Enum):
    SYSTEM = 100
    MEMORY = 90
    TOOLS = 80
    VISION = 70
    PLANNING = 60
    AGENTS = 50
    VOICE = 40
    CHAT = 10


class PolicyType(str, Enum):
    AUTO = "AUTO"
    TOOL_FIRST = "TOOL_FIRST"
    MEMORY_FIRST = "MEMORY_FIRST"
    CHAT_ONLY = "CHAT_ONLY"
    STRICT_SYSTEM = "STRICT_SYSTEM"


class EngineCapability(BaseModel):
    engine: str
    intents: List[IntentType]
    actions: List[str] = Field(default_factory=list)
    version: str = "1.0"


class RequestContext(BaseModel):
    message: str
    user_id: str = "default"
    session_id: str = "default"
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    active_goal_id: Optional[str] = None
    active_agent_id: Optional[str] = None
    active_plan_id: Optional[str] = None
    recent_memories: List[str] = Field(default_factory=list)
    system_state: str = "idle"
    voice_state: str = "idle"
    vision_state: str = "ready"
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    decision_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request: str
    context_summary: Dict[str, Any] = Field(default_factory=dict)
    candidate_engines: List[str] = Field(default_factory=list)
    chosen_engine: str
    chosen_action: Optional[str] = None
    reason: str
    confidence: float
    policy: PolicyType = PolicyType.AUTO
    execution_time_ms: float = 0.0
    formatter_used: str = "direct"
    success: bool = True
    fallback_used: bool = False
    action_graph_nodes: int = 1


class RouterMetrics(BaseModel):
    total_requests: int = 0
    intent_frequencies: Dict[str, int] = Field(default_factory=dict)
    average_routing_latency_ms: float = 0.0
    routing_accuracy: float = 1.0
    clarification_rate: float = 0.0
    fallback_rate: float = 0.0
    tool_success_rate: float = 1.0
    memory_hit_rate: float = 0.0


class SimulationRequest(BaseModel):
    message: str
    session_id: str = "default"


class SimulationResponse(BaseModel):
    intent: IntentType
    confidence: float
    policy: PolicyType
    engine: str
    action: Optional[str]
    will_execute: bool = False
    reasoning: str
