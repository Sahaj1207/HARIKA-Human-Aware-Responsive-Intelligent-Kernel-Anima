import logging
from datetime import datetime, timezone
from typing import Dict, Set
from app.agents.schemas import AgentStatus, AgentState

logger = logging.getLogger("harika.agents.state_machine")


class InvalidAgentStateTransitionError(ValueError):
    """Raised when an illegal or direct agent state transition is attempted."""
    pass


class AgentStateMachine:
    """Enforces strict agent lifecycle state transitions:
    CREATED -> READY -> RUNNING ↔ WAITING / PAUSED -> COMPLETED (or FAILED or CANCELLED).
    No illegal jumps allowed.
    """

    ALLOWED_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
        AgentState.CREATED: {AgentState.READY, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.READY: {AgentState.RUNNING, AgentState.PAUSED, AgentState.CANCELLED},
        AgentState.RUNNING: {AgentState.WAITING, AgentState.PAUSED, AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.WAITING: {AgentState.RUNNING, AgentState.PAUSED, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.PAUSED: {AgentState.RUNNING, AgentState.CANCELLED, AgentState.FAILED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: set(),
        AgentState.CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, current_state: AgentState, target_state: AgentState) -> bool:
        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        return target_state in allowed

    @classmethod
    def transition(cls, status: AgentStatus, target_state: AgentState) -> AgentStatus:
        if status.state == target_state:
            return status

        if not cls.can_transition(status.state, target_state):
            err_msg = (
                f"Illegal direct state transition for Agent '{status.agent_id}': "
                f"Cannot transition directly from '{status.state}' to '{target_state}'."
            )
            logger.error(f"[AgentStateMachine] {err_msg}")
            raise InvalidAgentStateTransitionError(err_msg)

        logger.info(f"[AgentStateMachine] Transitioned Agent '{status.agent_id}': {status.state} -> {target_state}")
        status.state = target_state
        status.updated_at = datetime.now(timezone.utc).isoformat()
        return status


agent_state_machine = AgentStateMachine()
