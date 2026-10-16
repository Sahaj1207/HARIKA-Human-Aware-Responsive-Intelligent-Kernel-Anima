from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import shutil
import tempfile
import unittest
from app.router.manager import router_manager
from app.presence.manager import presence_manager


class TestPresenceAllE2E(unittest.TestCase):

    def setUp(self):
        presence_manager.state.recent_failures.clear()
        presence_manager.state.current_goal = None

    def test_scenario1_memory_retrieval_dosa(self):
        loop = asyncio.new_event_loop()
        res1 = loop.run_until_complete(router_manager.route_request("My favourite drink is coffee", user_id="p_e2e"))
        res2 = loop.run_until_complete(router_manager.route_request("My favourite food is dosa", user_id="p_e2e"))

        query_res = loop.run_until_complete(router_manager.route_request("What is my favourite food", user_id="p_e2e"))
        loop.close()

        self.assertIn("dosa", query_res["response"].lower())

    def test_scenario2_memory_contradiction_biryani(self):
        loop = asyncio.new_event_loop()
        res1 = loop.run_until_complete(router_manager.route_request("My favourite food is dosa", user_id="p_e2e2"))
        res2 = loop.run_until_complete(router_manager.route_request("No. I like biryani now", user_id="p_e2e2"))

        query_res = loop.run_until_complete(router_manager.route_request("What do I like", user_id="p_e2e2"))
        loop.close()

        self.assertIn("biryani", query_res["response"].lower())

    def test_scenario3_continue_task(self):
        from app.agents.manager import agent_manager
        loop = asyncio.new_event_loop()
        agent_manager.create_agent(goal_id="goal-e2e-123", user_id="p_e2e")
        res = loop.run_until_complete(router_manager.route_request("continue"))
        agent_manager._agents.clear()
        loop.close()

        self.assertEqual(res["intent"], "AGENT_CONTINUE")



    def test_scenario4_repeated_build_failures(self):
        loop = asyncio.new_event_loop()
        presence_manager.state.recent_failures = ["f1", "f2"]
        res = loop.run_until_complete(router_manager.route_request("I keep getting a build error"))
        loop.close()

        self.assertIn("build failure", res["response"].lower())

    def test_scenario5_presentation_tomorrow_rehearsal(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(router_manager.route_request("I'm presenting tomorrow"))
        loop.close()

        self.assertIn("presentation", res["response"].lower())

    def test_scenario6_natural_tool_confirmation(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(router_manager.route_request("Calculate 125 * 48"))
        loop.close()

        self.assertEqual(res["response"], "125 * 48 = 6000")


if __name__ == "__main__":
    unittest.main()
