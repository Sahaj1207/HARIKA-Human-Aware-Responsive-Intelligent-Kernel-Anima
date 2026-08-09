import logging
from typing import Optional, List
from app.presence.schemas import ExperienceDecision, VerificationResult

logger = logging.getLogger("harika.presence.experience")


class ExperienceEngine:
    """Decides 'What creates the best experience right now?' (Executes AFTER verification, BEFORE communication)."""

    def evaluate_experience(
        self,
        verification: VerificationResult,
        message: str,
        recent_failures: Optional[List[str]] = None
    ) -> ExperienceDecision:
        msg = message.lower()
        failures = recent_failures or []

        if len(failures) >= 2 or "build error" in msg:
            logger.info("[ExperienceEngine] Created experience decision: offer_diagnostics.")
            return ExperienceDecision(
                decision="offer_diagnostics",
                reason="Repeated build failures detected.",
                tone_modifier="supportive_technical"
            )

        if "presenting tomorrow" in msg or "presentation tomorrow" in msg:
            logger.info("[ExperienceEngine] Created experience decision: offer_rehearsal.")
            return ExperienceDecision(
                decision="offer_rehearsal",
                reason="Upcoming presentation detected.",
                tone_modifier="encouraging"
            )

        return ExperienceDecision(
            decision="proceed",
            reason="Standard optimal user experience.",
            tone_modifier="calm_dependable"
        )


experience_engine = ExperienceEngine()
