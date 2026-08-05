import os
import shutil
import tempfile
import unittest
from pathlib import Path
from app.planning.schemas import GoalPriority, GoalStatus
from app.planning.goal_manager import GoalManager
from app.planning.events import planning_event_bus, PlanningEventType


class TestGoalManager(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.temp_storage = Path(self.test_dir) / "test_goals.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_goal_creation_and_priority_sorting(self):
        manager = GoalManager(storage_file=self.temp_storage)

        g_low = manager.create_goal("Low priority task", priority=GoalPriority.LOW)
        g_critical = manager.create_goal("Critical bugfix", priority=GoalPriority.CRITICAL)
        g_high = manager.create_goal("High priority feature", priority=GoalPriority.HIGH)
        g_bg = manager.create_goal("Background indexer", priority=GoalPriority.BACKGROUND)

        active_goals = manager.get_active_goals()
        priorities_in_order = [g.priority for g in active_goals]

        self.assertEqual(
            priorities_in_order,
            [
                GoalPriority.CRITICAL,
                GoalPriority.HIGH,
                GoalPriority.LOW,
                GoalPriority.BACKGROUND,
            ]
        )

    def test_goal_cancellation(self):
        manager = GoalManager(storage_file=self.temp_storage)
        events_received = []

        def on_cancel(event_type, payload):
            events_received.append((event_type, payload))

        planning_event_bus.subscribe(PlanningEventType.GOAL_CANCELLED, on_cancel)

        g = manager.create_goal("To be cancelled", priority=GoalPriority.NORMAL)
        self.assertEqual(g.status, GoalStatus.ACTIVE)

        result = manager.cancel_goal(g.id)
        self.assertTrue(result)
        self.assertEqual(manager.get_goal(g.id).status, GoalStatus.CANCELLED)
        self.assertEqual(len(manager.get_active_goals()), 0)
        self.assertTrue(any(e[1].get("id") == g.id for e in events_received))

    def test_goal_resumption_on_restart(self):
        # Manager 1 creates a goal
        manager1 = GoalManager(storage_file=self.temp_storage)
        g1 = manager1.create_goal("Persistent Goal", priority=GoalPriority.HIGH)

        # Manager 2 initializes using same storage file (simulating app restart)
        manager2 = GoalManager(storage_file=self.temp_storage)
        active_goals = manager2.get_active_goals()

        self.assertEqual(len(active_goals), 1)
        self.assertEqual(active_goals[0].id, g1.id)
        self.assertEqual(active_goals[0].title, "Persistent Goal")
        self.assertEqual(active_goals[0].priority, GoalPriority.HIGH)


if __name__ == "__main__":
    unittest.main()
