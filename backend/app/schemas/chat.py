from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., example="Hello HARIKA")
    user_name: Optional[str] = Field(default="User", example="Sahaj")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    spoken: bool = Field(default=False, description="The message came from speech recognition")


class ChatResponse(BaseModel):
    response: str = Field(..., example="Hello Sahaj.")
    provider: str = Field(..., example="ollama")
    model: str = Field(..., example="qwen3:latest")
    latency_ms: int = Field(..., example=1200)
    tone: str = Field(default="warm", description="How the reply should sound: warm, cheerful, empathetic, ...")
    learned: List[str] = Field(default_factory=list, description="Facts about the user HARIKA kept from this message")
