import unittest
from app.planning.schemas import PlanState, PlanStep
from app.planning.planner import HierarchicalPlanner
from app.planning.state_machine import PlanStateMachine, InvalidStateTransitionError


class TestPlanStateMachineAndPlanner(unittest.TestCase):

    def setUp(self):
        self.planner = HierarchicalPlanner()

    def test_normal_state_transitions(self):
        # Initial creation: CREATED -> VALIDATED -> READY
        plan = self.planner.create_plan(user_message="Build app")
        self.assertEqual(plan.state, PlanState.READY)
        self.assertEqual(plan.version, 1)
        self.assertEqual(plan.revision, 1)
        self.assertIsNotNone(plan.updated_at)

    def test_invalid_direct_transition_rejection(self):
        plan = self.planner.create_plan(user_message="Test plan")
        # Plan is currently READY. Attempting a direct transition to COMPLETED (skipping EXECUTING) must raise InvalidStateTransitionError
        with self.assertRaises(InvalidStateTransitionError):
            PlanStateMachine.transition(plan, PlanState.COMPLETED)

    def test_single_step_execution_steps_0(self):
        steps = [
            PlanStep(step_number=1, title="Step 1: Init"),
            PlanStep(step_number=2, title="Step 2: Build"),
            PlanStep(step_number=3, title="Step 3: Deploy"),
        ]
        plan = self.planner.create_plan(user_message="Deploy pipeline", custom_steps=steps)
        self.assertEqual(plan.state, PlanState.READY)

        # Sprint 10 executes ONLY steps[0]
        res = self.planner.execute_step_0(plan)
        self.assertEqual(res["executed_step"]["title"], "Step 1: Init")
        self.assertEqual(len(res["remaining_steps"]), 2)
        self.assertEqual(plan.state, PlanState.COMPLETED)

    def test_replanning_and_versioning(self):
        plan = self.planner.create_plan(user_message="Initial plan")
        self.assertEqual(plan.revision, 1)

        new_steps = [PlanStep(step_number=1, title="Updated Step 1")]
        replanned = self.planner.replan(plan, new_steps)

        self.assertEqual(replanned.revision, 2)
        self.assertEqual(replanned.state, PlanState.READY)

    def test_plan_cancellation(self):
        plan = self.planner.create_plan(user_message="Cancel target")
        cancelled_plan = self.planner.cancel_plan(plan)
        self.assertEqual(cancelled_plan.state, PlanState.CANCELLED)

        # Transitioning out of terminal state CANCELLED must fail
        with self.assertRaises(InvalidStateTransitionError):
            PlanStateMachine.transition(cancelled_plan, PlanState.READY)


if __name__ == "__main__":
    unittest.main()
