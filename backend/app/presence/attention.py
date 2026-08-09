import logging
from typing import Dict, Any, Optional
from app.presence.schemas import AttentionLevel, AttentionState

logger = logging.getLogger("harika.presence.attention")


class AttentionModel:
    """Evaluates what deserves attention right now across active tasks, errors, and directives."""

    def evaluate_attention(
        self,
        message: str,
        active_agent_id: Optional[str] = None,
        recent_failures: Optional[list] = None
    ) -> AttentionState:
        msg = message.lower()
        failures = recent_failures or []

        if active_agent_id:
            logger.info(f"[AttentionModel] Evaluated HIGHEST attention for active agent '{active_agent_id}'.")
            return AttentionState(
                level=AttentionLevel.HIGHEST,
                focus_topic=f"Agent Execution ({active_agent_id})",
                active_trigger="active_agent"
            )

        if len(failures) >= 2 or any(k in msg for k in ["build error", "compilation error", "failed", "exception", "bug"]):
            logger.info("[AttentionModel] Evaluated HIGH attention for failure/bug.")
            return AttentionState(
                level=AttentionLevel.HIGH,
                focus_topic="Error Diagnostics & Build Failure",
                active_trigger="build_failure"
            )

        if any(k in msg for k in ["calculate", "open ", "remember ", "what is ", "analyse", "plan"]):
            return AttentionState(
                level=AttentionLevel.MEDIUM,
                focus_topic="Subsystem Command Directive",
                active_trigger="command_directive"
            )

        return AttentionState(
            level=AttentionLevel.LOW,
            focus_topic="General Conversation",
            active_trigger="conversational_greeting"
        )


attention_model = AttentionModel()
