import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.tools.schemas import ToolStatusCode


class ToolResult(BaseModel):
    """Standardized result object returned by every tool execution."""

    execution_id: str = Field(default_factory=lambda: f"exec-{uuid.uuid4().hex[:8]}")
    success: bool
    verified: bool = False
    pid: Optional[int] = None
    process_name: Optional[str] = None
    status_code: ToolStatusCode
    tool_name: str
    execution_time_ms: float = 0.0
    output: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tool_version: str = "1.0.0"
    api_version: str = "v0.4"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


