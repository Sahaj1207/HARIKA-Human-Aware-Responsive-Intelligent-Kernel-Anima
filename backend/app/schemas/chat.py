from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., example="Hello HARIKA")
    user_name: Optional[str] = Field(default="User", example="Sahaj")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str = Field(..., example="Hello Sahaj.")
    provider: str = Field(..., example="ollama")
    model: str = Field(..., example="qwen3:latest")
    latency_ms: int = Field(..., example=1200)
