from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., example="online")
    app_name: str = Field(..., example="HARIKA-Core")
    version: str = Field(..., example="0.1.0")
    timestamp: str = Field(..., example="2026-08-03T01:00:00Z")


class SystemMetrics(BaseModel):
    status: str
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    active_services: int = 1
