from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MinimalSemanticIntent(BaseModel):
    """Small untrusted LLM-facing interpretation contract."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    operation: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SemanticRequest(BaseModel):
    """Provider-neutral, execution-free interpretation of a user request."""

    raw_text: str
    probable_goal: str
    operation: Optional[str] = None
    entities: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    candidate_capabilities: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    ambiguity: List[str] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    context_references: List[str] = Field(default_factory=list)
    validation_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(
            self.candidate_capabilities
            and self.confidence >= 0.0
            and not self.ambiguity
            and not self.validation_error
        )

    @property
    def needs_clarification(self) -> bool:
        return bool(self.ambiguity or self.clarification_question or self.validation_error)
