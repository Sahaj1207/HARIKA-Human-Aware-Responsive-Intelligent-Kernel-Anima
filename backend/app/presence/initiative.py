import logging
from typing import Optional
from app.presence.schemas import ExperienceDecision

logger = logging.getLogger("harika.presence.initiative")


class InitiativeEngine:
    """Initiative Engine offering proactive suggestions ONLY when confidence > 0.90 AND genuinely useful."""

    def evaluate_initiative(
        self,
        confidence: float,
        experience: ExperienceDecision
    ) -> Optional[str]:
        # Refinement 6: Intervene ONLY when confidence > 0.90
        if confidence < 0.90:
            return None

        if experience.decision == "offer_diagnostics":
            return "Offer build log diagnostics"
        elif experience.decision == "offer_rehearsal":
            return "Offer presentation Q&A rehearsal"

        return None


initiative_engine = InitiativeEngine()
