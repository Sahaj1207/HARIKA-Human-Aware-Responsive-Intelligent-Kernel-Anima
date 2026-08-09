import logging
from typing import Tuple
from app.router.schemas import IntentType, PolicyType

logger = logging.getLogger("harika.router.confidence")


class ConfidenceEstimator:
    """Evaluates classification confidence (0.0 -> 1.0). If < 0.60, requests clarification."""

    def evaluate(self, confidence: float, intent: IntentType) -> Tuple[bool, str]:
        if confidence < 0.60:
            msg = "Confidence score below threshold (< 0.60). Requesting clarification."
            logger.warning(f"[ConfidenceEstimator] {msg}")
            return True, msg
        return False, "Confidence score acceptable."


confidence_estimator = ConfidenceEstimator()
