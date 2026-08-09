import asyncio
import unittest
from app.router.manager import router_manager
from app.planning.goal_manager import goal_manager
from app.presence.workspace import workspace_manager


class TestStateManagementFixes(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_01_current_discussion_query_does_not_overwrite_discussion(self):
        """Verify that context queries (e.g. 'What are we talking about?') do NOT overwrite current_discussion in WorkspaceManager."""
        workspace_manager.clear()
        
        # Turn 1: Establish topic
        res1 = self.loop.run_until_complete(
            router_manager.route_request("Remember my favourite food is dosa", user_id="test_state_1")
        )
        disc_after_turn1 = workspace_manager.get_item("current_discussion")
        self.assertEqual(disc_after_turn1, "Remember my favourite food is dosa")

        # Turn 2: Ask context query
        res2 = self.loop.run_until_complete(
            router_manager.route_request("What are we talking about?", user_id="test_state_1")
        )
        resp2 = res2.get("response", "")
        disc_after_turn2 = workspace_manager.get_item("current_discussion")

        # Assertion: discussion remains turn 1 topic, response references turn 1 topic
        self.assertEqual(disc_after_turn2, "Remember my favourite food is dosa")
        self.assertIn("dosa", resp2.lower())
        self.assertNotIn("what are we talking about", resp2.lower())

    def test_02_stale_completed_goal_is_not_returned_as_active(self):
        """Verify that completed goals are marked completed and recent active goal is returned instead of stale goals."""
        # Create a mock completed agent goal execution
        goal = goal_manager.create_goal(title="Stale Completed Goal", description="Old goal")
        goal_manager.complete_goal(goal.id)

        # Create a new active goal
        new_goal = goal_manager.create_goal(title="Active Current Project", description="New active goal")

        # Query active goals
        active_goals = goal_manager.get_active_goals()
        self.assertTrue(len(active_goals) > 0)
        top_active = active_goals[0]

        # Assertion: top active goal is the newly created goal, not the completed goal
        self.assertEqual(top_active.id, new_goal.id)
        self.assertNotEqual(top_active.id, goal.id)

        # Route 'What am I working on?'
        res = self.loop.run_until_complete(
            router_manager.route_request("What am I working on?", user_id="test_state_2")
        )
        resp = res.get("response", "")
        self.assertIn("active current project", resp.lower())
        self.assertNotIn("calculate sqrt", resp.lower())

    def test_03_newly_created_plan_is_returned_by_show_plan(self):
        """Verify that 'Show plan' returns the plan newly created in the preceding turn rather than an older plan."""
        # Turn 1: Create plan
        res1 = self.loop.run_until_complete(
            router_manager.route_request("Plan for Sunday", user_id="test_state_3")
        )
        resp1 = res1.get("response", "")
        self.assertIn("plan created successfully", resp1.lower())

        # Turn 2: Show plan
        res2 = self.loop.run_until_complete(
            router_manager.route_request("Show plan", user_id="test_state_3")
        )
        resp2 = res2.get("response", "")

        # Assertion: response returns the plan for Sunday, not a stale old plan
        self.assertIn("plan for sunday", resp2.lower())
        self.assertNotIn("calculate sqrt", resp2.lower())


if __name__ == "__main__":
    unittest.main()
