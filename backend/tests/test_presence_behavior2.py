import asyncio
import unittest
from app.router.manager import router_manager
from app.presence.manager import presence_manager


class TestPresenceBehaviorFixesSprint2(unittest.TestCase):

    def setUp(self):
        presence_manager.state.recent_failures.clear()
        presence_manager.state.current_goal = None

    def test_bug1_greeting_and_social_conversation(self):
        loop = asyncio.new_event_loop()
        res_hello = loop.run_until_complete(router_manager.route_request("Hello"))
        res_how = loop.run_until_complete(router_manager.route_request("How are you?"))
        res_thanks = loop.run_until_complete(router_manager.route_request("Thanks"))
        res_bye = loop.run_until_complete(router_manager.route_request("Bye"))
        loop.close()

        self.assertIn("Hello, Sahaj", res_hello["response"])
        self.assertTrue(any(k in res_how["response"].lower() for k in ["doing well", "functioning smoothly", "systems operational"]))
        self.assertEqual(res_thanks["response"], "You're welcome!")
        self.assertEqual(res_bye["response"], "See you later.")

    def test_bug2_honest_tool_execution_state_reporting(self):
        async def dummy_failed_executor():
            return {
                "status": "failed",
                "success": False,
                "tool": "open_website",
                "error": "desktop execution isn't available"
            }

        async def dummy_success_executor():
            return {
                "status": "success",
                "success": True,
                "tool": "open_website",
                "result": {"url": "https://github.com"}
            }

        loop = asyncio.new_event_loop()

        # Failed execution test
        res_fail = loop.run_until_complete(
            presence_manager.process_directive(
                intent="TOOL_EXECUTION",
                engine_name="ToolManager",
                raw_message="Open GitHub",
                subsystem_executor_fn=dummy_failed_executor
            )
        )
        self.assertTrue("couldn't open" in res_fail.natural_response.lower() or "couldn't verify" in res_fail.natural_response.lower())
        self.assertIn("isn't available", res_fail.natural_response.lower())


        # Success execution test
        res_success = loop.run_until_complete(
            presence_manager.process_directive(
                intent="TOOL_EXECUTION",
                engine_name="ToolManager",
                raw_message="Open GitHub",
                subsystem_executor_fn=dummy_success_executor
            )
        )
        self.assertIn("opened github", res_success.natural_response.lower())

        loop.close()


if __name__ == "__main__":
    unittest.main()
