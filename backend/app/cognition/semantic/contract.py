from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MinimalSemanticIntent(BaseModel):
    """Small untrusted LLM-facing interpretation contract (single action)."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    operation: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SemanticAction(BaseModel):
    """One step of the ordered, untrusted LLM action list ("Format C")."""

    model_config = ConfigDict(extra="forbid")

    operation: str = Field(validation_alias=AliasChoices("operation", "action"))
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    goal: Optional[str] = None


class SemanticPlan(BaseModel):
    """Ordered actions; an empty list means the message is not a capability request."""

    model_config = ConfigDict(extra="forbid")

    actions: List[SemanticAction] = Field(default_factory=list, max_length=5)


class ResolvedStep(BaseModel):
    """A semantic action after validation against the registered capability catalog."""

    operation: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    capability: str
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


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
    steps: List[ResolvedStep] = Field(default_factory=list)
    is_conversational: bool = False

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
