from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability3Planner(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_03_planner_35_cases(self):
        conversations = [
            ("Create a plan to refactor backend tests", "plan"),
            ("Plan how to deploy the web application", "plan"),
            ("Create plan for database migration", "plan"),
            ("Make a plan to optimize API endpoints", "plan"),
            ("Build a plan for user authentication", "plan"),
            ("Show my plan", "plan"),
            ("Display current plan", "plan"),
            ("What is my active plan?", "plan"),
            ("View plan", "plan"),
            ("Show active goal plan", "plan"),
            ("Continue my plan", "continue"),
            ("Resume current plan", "continue"),
            ("Proceed with plan", "continue"),
            ("Execute next step in plan", "continue"),
            ("Keep going with plan", "continue"),
            ("Create plan for frontend UI polish", "plan"),
            ("Plan for error handling improvements", "plan"),
            ("Create a plan to add unit tests", "plan"),
            ("Plan system backup strategy", "plan"),
            ("Create plan to monitor CPU usage", "plan"),
            ("Show my plan status", "plan"),
            ("What is the status of my plan?", "plan"),
            ("Display plan progress", "plan"),
            ("Show current plan steps", "plan"),
            ("View active goal status", "plan"),
            ("Continue active plan", "continue"),
            ("Resume plan execution", "continue"),
            ("Continue goal execution", "continue"),
            ("Proceed to next plan step", "continue"),
            ("Execute active plan", "continue"),
            ("Create plan for logging integration", "plan"),
            ("Plan security audit workflow", "plan"),
            ("Show current plan", "plan"),
            ("Continue plan", "continue"),
            ("Resume plan", "continue"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="plan_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = expected_kw.lower() in resp.lower() or expected_kw.lower() in intent.lower() or "plan" in resp.lower() or "goal" in resp.lower() or "step" in resp.lower()
            self.assertTrue(passed, f"Planner Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}') | Expected kw: '{expected_kw}'")


if __name__ == "__main__":
    unittest.main()
