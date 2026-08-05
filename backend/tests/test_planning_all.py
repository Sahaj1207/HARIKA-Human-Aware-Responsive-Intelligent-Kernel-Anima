import shutil
import tempfile
import unittest
from pathlib import Path

from app.planning.schemas import GoalPriority, GoalStatus, PlanState, DecisionStrategy
from app.planning.goal_manager import GoalManager
from app.planning.task_manager import TaskManager
from app.planning.decision_engine import DecisionEngine
from app.planning.planner import HierarchicalPlanner
from app.planning.reflection import ReflectionEngine
from app.planning.history import PlanHistory
from app.planning.manager import PlanningManager
from app.planning.state_machine import PlanStateMachine, InvalidStateTransitionError
from app.planning.events import planning_event_bus, PlanningEventType


class TestPlanningEngine10Requirements(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.goals_file = Path(self.test_dir) / "goals.json"
        self.tasks_file = Path(self.test_dir) / "tasks.json"
        self.history_file = Path(self.test_dir) / "history.json"

        self.goals = GoalManager(storage_file=self.goals_file)
        self.tasks = TaskManager(storage_file=self.tasks_file)
        self.decisions = DecisionEngine(confidence_threshold=0.70)
        self.planner = HierarchicalPlanner()
        self.reflections = ReflectionEngine()
        self.history = PlanHistory(history_file=self.history_file)

        self.manager = PlanningManager(
            goals=self.goals,
            tasks=self.tasks,
            decisions=self.decisions,
            planner=self.planner,
            reflections=self.reflections,
            history=self.history
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. PLAN STATE MACHINE
    def test_req1_plan_state_machine_strictness(self):
        plan = self.manager.create_plan("Test State Machine")
        self.assertEqual(plan.state, PlanState.READY)
        # Attempting direct jump to COMPLETED without EXECUTING must fail
        with self.assertRaises(InvalidStateTransitionError):
            PlanStateMachine.transition(plan, PlanState.COMPLETED)

    # 2. GOAL PRIORITIES
    def test_req2_goal_priorities_ordering(self):
        self.manager.create_goal("Low Goal", priority=GoalPriority.LOW)
        self.manager.create_goal("Critical Goal", priority=GoalPriority.CRITICAL)
        self.manager.create_goal("High Goal", priority=GoalPriority.HIGH)
        self.manager.create_goal("Background Goal", priority=GoalPriority.BACKGROUND)

        active = self.manager.get_active_goals()
        priorities = [g.priority for g in active]
        self.assertEqual(priorities, [
            GoalPriority.CRITICAL,
            GoalPriority.HIGH,
            GoalPriority.LOW,
            GoalPriority.BACKGROUND
        ])

    # 3. TASK DEPENDENCIES
    def test_req3_task_dependencies_lock(self):
        g = self.manager.create_goal("Task Dep Goal")
        t1 = self.manager.create_task(goal_id=g.id, title="Prerequisite")
        t2 = self.manager.create_task(goal_id=g.id, title="Dependent", depends_on=[t1.id])

        self.assertFalse(self.manager.can_execute_task(t2.id))
        self.assertFalse(self.manager.complete_task(t2.id))

        self.manager.complete_task(t1.id)
        self.assertTrue(self.manager.can_execute_task(t2.id))
        self.assertTrue(self.manager.complete_task(t2.id))

    # 4. DECISION CONFIDENCE
    def test_req4_decision_confidence_thresholding(self):
        # High confidence -> normal evaluation
        d1 = self.manager.evaluate_decision("Please remember my preference")
        self.assertEqual(d1.strategy, DecisionStrategy.RETRIEVE_MEMORY)

        # Low confidence (< 0.70 threshold) -> forced ASK_CLARIFICATION without guessing
        d2 = self.decisions.evaluate_decision("Run script", is_tool_action=True, tool_name="unknown", override_confidence=0.50)
        self.assertEqual(d2.strategy, DecisionStrategy.ASK_CLARIFICATION)
        self.assertIsNone(d2.selected_tool)

    # 5. REFLECTION QUALITY
    def test_req5_reflection_quality_no_chain_of_thought(self):
        refl = self.manager.record_reflection("Direct prompt", "Response text", success=True)
        dump = refl.model_dump()
        self.assertIn("summary", dump)
        self.assertIn("outcome", dump)
        self.assertIn("success", dump)
        self.assertIn("confidence", dump)
        self.assertIn("lessons_learned", dump)
        self.assertIn("next_recommendation", dump)
        self.assertNotIn("chain_of_thought", dump)
        self.assertNotIn("reasoning", dump)

    # 6. PLAN VERSIONING
    def test_req6_plan_versioning(self):
        plan = self.manager.create_plan("Versioned plan")
        self.assertEqual(plan.version, 1)
        self.assertEqual(plan.revision, 1)
        self.assertIsNotNone(plan.updated_at)

        replanned = self.manager.replan(plan, plan.steps)
        self.assertEqual(replanned.revision, 2)

    # 7. PLAN CANCELLATION
    def test_req7_cancellation_cascade(self):
        g = self.manager.create_goal("Goal to Cancel")
        t = self.manager.create_task(goal_id=g.id, title="Task to Cancel")
        p = self.manager.create_plan("Plan to Cancel")

        self.assertTrue(self.manager.cancel_goal(g.id))
        self.assertTrue(self.manager.cancel_task(t.id))
        cancelled_p = self.manager.cancel_plan(p)

        self.assertEqual(self.manager.get_goal(g.id).status, GoalStatus.CANCELLED)
        self.assertEqual(self.tasks.get_task(t.id).status, "cancelled")
        self.assertEqual(cancelled_p.state, PlanState.CANCELLED)

    # 8. GOAL RESUMPTION
    def test_req8_goal_resumption(self):
        g = self.goals.create_goal("Resumable Goal", priority=GoalPriority.HIGH)
        # Instantiate new GoalManager simulating app restart
        restarted_goals = GoalManager(storage_file=self.goals_file)
        active = restarted_goals.get_active_goals()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].id, g.id)

    # 9. PLANNING EVENTS
    def test_req9_planning_events_emitted(self):
        emitted_events = []
        def listener(et, p):
            emitted_events.append(et)

        for event_type in PlanningEventType:
            planning_event_bus.subscribe(event_type, listener)

        g = self.manager.create_goal("Event Goal")
        self.manager.cancel_goal(g.id)

        self.assertIn(PlanningEventType.GOAL_CREATED.value, emitted_events)
        self.assertIn(PlanningEventType.GOAL_CANCELLED.value, emitted_events)

    # 10. FUTURE MULTI-STEP EXECUTION
    def test_req10_multi_step_single_execution_steps_0(self):
        plan = self.manager.create_plan("Multi step plan")
        self.assertEqual(plan.state, PlanState.READY)
        res = self.manager.execute_step_0(plan)
        self.assertEqual(res["status"], "success")
        self.assertEqual(plan.state, PlanState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
