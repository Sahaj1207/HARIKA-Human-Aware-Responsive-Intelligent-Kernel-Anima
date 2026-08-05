import logging
from datetime import datetime, timezone
from app.planning.schemas import Plan, PlanState

logger = logging.getLogger("harika.planning.state_machine")


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal or direct state machine transition is attempted."""
    pass


class PlanStateMachine:
    """Enforces strict sequential plan state transitions:
    CREATED -> VALIDATED -> READY -> EXECUTING -> COMPLETED (or FAILED or CANCELLED).
    No direct jumps allowed.
    """

    ALLOWED_TRANSITIONS = {
        PlanState.CREATED: {PlanState.VALIDATED, PlanState.FAILED, PlanState.CANCELLED},
        PlanState.VALIDATED: {PlanState.READY, PlanState.FAILED, PlanState.CANCELLED},
        PlanState.READY: {PlanState.EXECUTING, PlanState.CANCELLED},
        PlanState.EXECUTING: {PlanState.COMPLETED, PlanState.FAILED, PlanState.CANCELLED},
        PlanState.COMPLETED: set(),
        PlanState.FAILED: set(),
        PlanState.CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, current_state: PlanState, target_state: PlanState) -> bool:
        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        return target_state in allowed

    @classmethod
    def transition(cls, plan: Plan, target_state: PlanState) -> Plan:
        if plan.state == target_state:
            return plan

        if not cls.can_transition(plan.state, target_state):
            err_msg = (
                f"Illegal direct state transition for Plan '{plan.id}': "
                f"Cannot transition directly from '{plan.state}' to '{target_state}'."
            )
            logger.error(f"[PlanStateMachine] {err_msg}")
            raise InvalidStateTransitionError(err_msg)

        logger.info(f"[PlanStateMachine] Transitioned Plan '{plan.id}': {plan.state} -> {target_state}")
        plan.state = target_state
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        return plan


plan_state_machine = PlanStateMachine()
