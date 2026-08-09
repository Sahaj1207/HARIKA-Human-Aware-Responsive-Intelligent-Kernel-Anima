import logging
from typing import Optional

logger = logging.getLogger("harika.presence.clarification")


class ClarificationEngine:
    """Generates natural clarification questions when confidence is below threshold."""

    def generate_clarification(self, confidence: float, topic: Optional[str] = None) -> str:
        logger.info(f"[ClarificationEngine] Generated clarification for topic '{topic}' (conf={confidence}).")
        if topic:
            return f"I want to make sure I understand correctly regarding {topic}. Could you clarify your objective?"
        return "I want to be sure I get this right for you. Could you clarify what you'd like me to do?"


clarification_engine = ClarificationEngine()
