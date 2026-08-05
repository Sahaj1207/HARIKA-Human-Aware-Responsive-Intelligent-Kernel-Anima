import shutil
import tempfile
import unittest
from pathlib import Path
from app.planning.schemas import GoalPriority, PlanState, DecisionStrategy
from app.planning.goal_manager import GoalManager
from app.planning.task_manager import TaskManager
from app.planning.decision_engine import DecisionEngine
from app.planning.planner import HierarchicalPlanner
from app.planning.reflection import ReflectionEngine
from app.planning.history import PlanHistory
from app.planning.manager import PlanningManager


class TestPlanningManagerFacade(unittest.TestCase):

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

    def test_facade_end_to_end_flow(self):
        # 1. Create Goal with CRITICAL priority
        goal = self.manager.create_goal(title="Critical Infrastructure Upgrade", priority=GoalPriority.CRITICAL)
        self.assertEqual(goal.priority, GoalPriority.CRITICAL)

        # 2. Create Dependent Tasks
        t1 = self.manager.create_task(goal_id=goal.id, title="Task 1: Setup DB")
        t2 = self.manager.create_task(goal_id=goal.id, title="Task 2: Migrate Schemas", depends_on=[t1.id])

        self.assertFalse(self.manager.can_execute_task(t2.id))
        self.manager.complete_task(t1.id)
        self.assertTrue(self.manager.can_execute_task(t2.id))

        # 3. Decision Evaluation
        decision = self.manager.evaluate_decision("Please remember DB password")
        self.assertEqual(decision.strategy, DecisionStrategy.RETRIEVE_MEMORY)

        # 4. Create Plan & Execute Step 0 strictly
        plan = self.manager.create_plan(user_message="Migrate DB", goal_id=goal.id)
        self.assertEqual(plan.state, PlanState.READY)

        res = self.manager.execute_step_0(plan)
        self.assertEqual(plan.state, PlanState.COMPLETED)
        self.assertEqual(res["status"], "success")

        # 5. Record Reflection
        refl = self.manager.record_reflection("Migrate DB", "Success", success=True)
        self.assertTrue(refl.success)

        # 6. Check metrics & history
        history = self.manager.get_history()
        self.assertGreater(len(history), 0)


if __name__ == "__main__":
    unittest.main()
