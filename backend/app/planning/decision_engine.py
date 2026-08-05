import logging
from typing import Dict, Any, Optional
from app.planning.schemas import Decision, DecisionStrategy
from app.planning.events import planning_event_bus, PlanningEventType

logger = logging.getLogger("harika.planning.decision")



class DecisionEngine:
    """Evaluates input context to select response strategy with strict configurable confidence thresholding."""

    def __init__(self, confidence_threshold: float = 0.65):
        self.confidence_threshold = confidence_threshold

    def evaluate_decision(
        self,
        user_message: str,
        is_tool_action: bool = False,
        tool_name: Optional[str] = None,
        override_confidence: Optional[float] = None
    ) -> Decision:
        msg_lower = user_message.lower().strip()

        # Check explicit tool action trigger
        if is_tool_action and tool_name:
            confidence = override_confidence if override_confidence is not None else 0.95
            decision = Decision(
                strategy=DecisionStrategy.EXECUTE_TOOL,
                reason=f"Action Engine identified tool trigger for '{tool_name}'.",
                confidence=confidence,
                selected_tool=tool_name
            )
        # Check ambiguous or extremely short directives
        elif len(msg_lower) <= 2 and msg_lower not in ["hi", "ok", "no"]:
            confidence = override_confidence if override_confidence is not None else 0.40
            decision = Decision(
                strategy=DecisionStrategy.ASK_CLARIFICATION,
                reason="Directive is underspecified or ambiguous.",
                confidence=confidence,
                selected_tool=None
            )
        # Memory search keyword triggers
        elif any(kw in msg_lower for kw in ["remember", "favourite", "project", "my name", "what is my"]):
            confidence = override_confidence if override_confidence is not None else 0.90
            decision = Decision(
                strategy=DecisionStrategy.RETRIEVE_MEMORY,
                reason="Context indicates memory retrieval requirement.",
                confidence=confidence,
                selected_tool=None
            )
        else:
            confidence = override_confidence if override_confidence is not None else 0.88
            decision = Decision(
                strategy=DecisionStrategy.RESPOND_NORMALLY,
                reason="Standard conversational query.",
                confidence=confidence,
                selected_tool=None
            )

        # Enforce Confidence Threshold rule: if confidence < threshold, ask clarification (Never guess)
        if decision.confidence < self.confidence_threshold:
            logger.info(
                f"[DecisionEngine] Decision confidence ({decision.confidence}) below threshold ({self.confidence_threshold}). "
                f"Forcing ASK_CLARIFICATION (Never guess)."
            )
            decision.strategy = DecisionStrategy.ASK_CLARIFICATION
            decision.reason = f"Decision confidence ({decision.confidence}) below threshold ({self.confidence_threshold}). Clarification required."
            decision.selected_tool = None

        planning_event_bus.emit(PlanningEventType.DECISION_MADE, decision.model_dump())
        return decision


decision_engine = DecisionEngine()

