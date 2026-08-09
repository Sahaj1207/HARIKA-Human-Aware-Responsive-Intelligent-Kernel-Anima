from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.router.schemas import IntentType


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float
    reason: str
    target_engine: str
    target_action: Optional[str] = None
    parameters: Dict[str, Any] = {}
