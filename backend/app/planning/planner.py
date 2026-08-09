import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.planning.schemas import Plan, PlanStep, PlanState
from app.planning.validator import plan_validator, PlanValidator
from app.planning.state_machine import PlanStateMachine, InvalidStateTransitionError

logger = logging.getLogger("harika.planning.planner")



class HierarchicalPlanner:
    """Constructs structured multi-step plans with versioning, single-step execution, and strict state transitions."""

    def __init__(self, validator: Optional[PlanValidator] = None):
        self.validator = validator or plan_validator
        self.state_machine = PlanStateMachine()

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "subsystem": "HierarchicalPlanner",
            "name": "Goal & Task Planning Engine",
            "features": ["Multi-step Plan Generation", "State Machine Validation", "Goal Decomposition"]
        }

    def get_plan_status(self, query: str = "") -> Dict[str, Any]:
        from app.planning.goal_manager import goal_manager
        active_goals = goal_manager.get_active_goals()
        if active_goals:
            top_g = active_goals[0]
            return {
                "status": "plan_query",
                "has_plan": True,
                "plan_title": top_g.title,
                "progress": top_g.progress,
                "goal_id": top_g.id,
                "summary": f"Your active plan is: '{top_g.title}' (Progress: {int(top_g.progress)}%)."
            }
        return {
            "status": "plan_query",
            "has_plan": False,
            "summary": "You don't have an active plan right now."
        }


    def create_plan(

        self,
        user_message: str,
        goal_id: Optional[str] = None,
        tool_action: Optional[Dict[str, Any]] = None,
        custom_steps: Optional[List[PlanStep]] = None
    ) -> Plan:
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        if not goal_id:
            from app.planning.goal_manager import goal_manager
            goal = goal_manager.create_goal(title=f"Goal for '{user_message}'", description=user_message)
            goal_id = goal.id

        steps: List[PlanStep] = custom_steps or []


        if not steps:
            if tool_action:
                steps.append(
                    PlanStep(
                        step_number=1,
                        title=f"Execute {tool_action.get('tool_name', 'tool')} action",
                        tool_name=tool_action.get("tool_name"),
                        arguments=tool_action.get("arguments", {}),
                        reasoning=tool_action.get("reasoning", "Tool action requested.")
                    )
                )
            else:
                steps.append(
                    PlanStep(
                        step_number=1,
                        title="Generate conversational response",
                        reasoning="Standard conversational query."
                    )
                )

        plan = Plan(
            id=plan_id,
            goal_id=goal_id,
            state=PlanState.CREATED,
            steps=steps,
            version=1,
            revision=1,
            updated_at=datetime.now(timezone.utc).isoformat()
        )

        # 1. State Machine: CREATED -> VALIDATED
        val_report = self.validator.validate_plan(plan)
        if val_report.is_valid:
            self.state_machine.transition(plan, PlanState.VALIDATED)
            # 2. State Machine: VALIDATED -> READY
            self.state_machine.transition(plan, PlanState.READY)
            logger.info(f"[HierarchicalPlanner] Plan {plan_id} v1.1 validated & READY ({len(steps)} steps).")
        else:
            self.state_machine.transition(plan, PlanState.FAILED)
            logger.warning(f"[HierarchicalPlanner] Plan {plan_id} validation failed: {val_report.errors}")

        return plan

    def execute_step_0(self, plan: Plan) -> Dict[str, Any]:
        """Sprint 10 single-step execution: Executes ONLY steps[0].
        State transitions: READY -> EXECUTING -> COMPLETED (or FAILED).
        Architecture supports future execution loops without looping now.
        """
        if not plan.steps:
            raise ValueError(f"Plan {plan.id} contains no execution steps.")

        # Transition READY -> EXECUTING
        self.state_machine.transition(plan, PlanState.EXECUTING)

        step_to_execute = plan.steps[0]
        logger.info(f"[HierarchicalPlanner] Sprint 10 executing ONLY steps[0]: {step_to_execute.title}")

        execution_result = {
            "plan_id": plan.id,
            "executed_step": step_to_execute.model_dump(),
            "remaining_steps": [s.model_dump() for s in plan.steps[1:]],
            "status": "success"
        }

        # Transition EXECUTING -> COMPLETED
        self.state_machine.transition(plan, PlanState.COMPLETED)
        return execution_result

    def replan(self, plan: Plan, new_steps: List[PlanStep]) -> Plan:
        """Replans an existing plan by incrementing revision and re-validating steps."""
        plan.steps = new_steps
        plan.revision += 1
        plan.updated_at = datetime.now(timezone.utc).isoformat()

        # Reset state machine to CREATED and transition through VALIDATED -> READY
        plan.state = PlanState.CREATED
        val_report = self.validator.validate_plan(plan)
        if val_report.is_valid:
            self.state_machine.transition(plan, PlanState.VALIDATED)
            self.state_machine.transition(plan, PlanState.READY)
        else:
            self.state_machine.transition(plan, PlanState.FAILED)

        logger.info(f"[HierarchicalPlanner] Replanned Plan {plan.id} to rev {plan.revision}.")
        return plan

    def cancel_plan(self, plan: Plan) -> Plan:
        """Cleanly transitions plan to CANCELLED state via PlanStateMachine."""
        return self.state_machine.transition(plan, PlanState.CANCELLED)


hierarchical_planner = HierarchicalPlanner()

