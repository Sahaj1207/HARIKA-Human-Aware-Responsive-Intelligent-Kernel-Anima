from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ToolStatusCode(str, Enum):
    SUCCESS = "SUCCESS"
    TOOL_DISABLED = "TOOL_DISABLED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_INSTALLED = "NOT_INSTALLED"
    TIMEOUT = "TIMEOUT"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    TOOL_BUSY = "TOOL_BUSY"
    UNKNOWN = "UNKNOWN"


class PermissionLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PermissionCachePolicy(str, Enum):
    ALWAYS_ALLOW = "ALWAYS_ALLOW"
    ALLOW_ONCE = "ALLOW_ONCE"
    ALWAYS_DENY = "ALWAYS_DENY"


class ToolHealth(BaseModel):
    available: bool = True
    reason: str = "Operational"
    dependencies: List[str] = Field(default_factory=list)


class ToolManifest(BaseModel):
    name: str = Field(..., description="Unique tool identifier string")
    display_name: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Detailed description of tool capabilities")
    version: str = Field(default="1.0.0", description="Tool version string")
    author: str = Field(default="HARIKA OS Core", description="Author or plugin origin")
    category: str = Field(default="system", description="Tool category classification")
    permissions: PermissionLevel = Field(default=PermissionLevel.NONE, description="Permission risk level")
    enabled: bool = Field(default=True, description="Enable / disable toggle state")
    platforms: List[str] = Field(default_factory=lambda: ["windows", "linux", "darwin"], description="Supported OS platforms")


class SingleAction(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reasoning: Optional[str] = None


class ActionPlan(BaseModel):
    is_tool_action: bool = False
    actions: List[SingleAction] = Field(default_factory=list)
    confidence: float = 1.0


class ToolMetrics(BaseModel):
    total_tools: int
    enabled_tools: int
    total_executions: int
    success_rate: float
    failure_rate: float
    average_duration_ms: float
    most_used_tool: Optional[str] = None
