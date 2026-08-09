import asyncio
import unittest
from app.router.manager import router_manager
from app.presence.manager import presence_manager


class TestPresenceBehaviorFixesSprint3(unittest.TestCase):

    def setUp(self):
        presence_manager.state.recent_failures.clear()
        presence_manager.state.current_goal = None

    def test_bug1_verified_tool_execution(self):
        async def dummy_verified_executor():
            return {
                "status": "success",
                "success": True,
                "verified": True,
                "tool": "open_website",
                "result": {"url": "https://github.com"}
            }

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            presence_manager.process_directive(
                intent="TOOL_EXECUTION",
                engine_name="ToolManager",
                raw_message="Open GitHub",
                subsystem_executor_fn=dummy_verified_executor
            )
        )
        loop.close()

        self.assertIn("opened github", res.natural_response.lower())

    def test_bug2_unverified_tool_execution(self):
        async def dummy_unverified_executor():
            return {
                "status": "failed",
                "success": False,
                "verified": False,
                "tool": "open_website",
                "error": "desktop execution isn't available"
            }

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            presence_manager.process_directive(
                intent="TOOL_EXECUTION",
                engine_name="ToolManager",
                raw_message="Open GitHub",
                subsystem_executor_fn=dummy_unverified_executor
            )
        )
        loop.close()

        self.assertTrue("couldn't open" in res.natural_response.lower() or "couldn't verify" in res.natural_response.lower())
        self.assertIn("desktop execution isn't available", res.natural_response.lower())

    def test_bug3_and_bug4_execution_feedback_retry_and_recovery(self):
        async def dummy_unverified_executor():
            return {
                "status": "failed",
                "success": False,
                "verified": False,
                "tool": "open_website",
                "error": "desktop execution isn't available"
            }

        loop = asyncio.new_event_loop()

        # Step 1: User asks Open GitHub (fails)
        res1 = loop.run_until_complete(
            presence_manager.process_directive(
                intent="TOOL_EXECUTION",
                engine_name="ToolManager",
                raw_message="Open GitHub",
                subsystem_executor_fn=dummy_unverified_executor
            )
        )
        self.assertTrue("couldn't open" in res1.natural_response.lower() or "couldn't verify" in res1.natural_response.lower())


        # Step 2: User says "Still closed." (Triggers EXECUTION_FEEDBACK, 1 automatic retry, then honest recovery)
        res2 = loop.run_until_complete(
            router_manager.route_request("Still closed")
        )
        loop.close()

        self.assertIn("you're right", res2["response"].lower())
        self.assertIn("launch wasn't successful", res2["response"].lower())
        self.assertNotIn("here's what i found", res2["response"].lower())


if __name__ == "__main__":
    unittest.main()
