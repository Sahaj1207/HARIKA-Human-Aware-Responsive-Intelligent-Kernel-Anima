import logging
from typing import Optional
from app.presence.schemas import GoalInference

logger = logging.getLogger("harika.presence.goal_inference")


class GoalInferenceEngine:
    """Infers user's real implicit objective from prompt context."""

    def infer_goal(self, message: str) -> Optional[GoalInference]:
        clean = message.lower()

        if "presenting tomorrow" in clean or "presentation tomorrow" in clean or "demo tomorrow" in clean:
            logger.info("[GoalInference] Inferred presentation preparation goal.")
            return GoalInference(
                inferred_goal="Presentation Preparation",
                confidence=0.92,
                suggestion="Would you like to rehearse with a mock Q&A session?",
                reason="User mentioned upcoming presentation tomorrow."
            )

        if "build error" in clean or "compilation error" in clean or "same error" in clean:
            logger.info("[GoalInference] Inferred debug project goal.")
            return GoalInference(
                inferred_goal="Project Debugging & Error Diagnosis",
                confidence=0.94,
                suggestion="Shall I inspect the build logs to diagnose the issue?",
                reason="User reported repeated build compilation failure."
            )

        return None


goal_inference_engine = GoalInferenceEngine()
