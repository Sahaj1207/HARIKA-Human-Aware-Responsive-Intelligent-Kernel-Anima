import os
import shutil
import tempfile
import unittest
from pathlib import Path
from app.planning.schemas import GoalPriority
from app.planning.task_manager import TaskManager
from app.planning.events import planning_event_bus, PlanningEventType


class TestTaskManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.temp_storage = Path(self.test_dir) / "test_tasks.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_task_creation_and_events(self):
        manager = TaskManager(storage_file=self.temp_storage)
        created_events = []

        def on_create(event_type, payload):
            created_events.append((event_type, payload))

        planning_event_bus.subscribe(PlanningEventType.TASK_CREATED, on_create)

        t1 = manager.create_task(goal_id="goal-1", title="Setup Environment")
        self.assertEqual(t1.title, "Setup Environment")
        self.assertFalse(t1.completed)
        self.assertTrue(any(e[1].get("id") == t1.id for e in created_events))

    def test_task_dependencies_refusal(self):
        manager = TaskManager(storage_file=self.temp_storage)

        # Task 1 has no dependencies
        t1 = manager.create_task(goal_id="goal-1", title="Task 1")

        # Task 2 depends on Task 1
        t2 = manager.create_task(goal_id="goal-1", title="Task 2", depends_on=[t1.id])

        # Task 2 cannot execute before Task 1 completes
        self.assertTrue(manager.can_execute_task(t1.id))
        self.assertFalse(manager.can_execute_task(t2.id))

        # Attempting to complete Task 2 directly should fail due to unmet dependencies
        completion_result = manager.complete_task(t2.id)
        self.assertFalse(completion_result)

        # Complete Task 1
        manager.complete_task(t1.id)

        # Now Task 2 can execute and complete
        self.assertTrue(manager.can_execute_task(t2.id))
        self.assertTrue(manager.complete_task(t2.id))
        self.assertTrue(t2.completed)

    def test_task_cancellation(self):
        manager = TaskManager(storage_file=self.temp_storage)
        t = manager.create_task(goal_id="goal-1", title="Task to cancel")
        self.assertTrue(manager.cancel_task(t.id))
        self.assertEqual(manager.get_task(t.id).status, "cancelled")
        self.assertFalse(manager.can_execute_task(t.id))

    def test_task_resumption_from_storage(self):
        manager1 = TaskManager(storage_file=self.temp_storage)
        t1 = manager1.create_task(goal_id="goal-100", title="Persistent Task")

        manager2 = TaskManager(storage_file=self.temp_storage)
        tasks_for_goal = manager2.get_tasks_for_goal("goal-100")
        self.assertEqual(len(tasks_for_goal), 1)
        self.assertEqual(tasks_for_goal[0].id, t1.id)


if __name__ == "__main__":
    unittest.main()
