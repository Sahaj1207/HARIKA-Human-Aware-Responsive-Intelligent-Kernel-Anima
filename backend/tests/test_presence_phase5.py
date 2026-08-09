import asyncio
import unittest
from app.presence.manager import presence_manager
from app.router.manager import router_manager


class TestPresencePhase5(unittest.TestCase):

    def test_presence_manager_process_directive(self):
        async def dummy_executor():
            return {"status": "success", "result": "dummy_output"}

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            presence_manager.process_directive(
                intent="CHAT",
                engine_name="CognitionManager",
                raw_message="Hello HARIKA",
                subsystem_executor_fn=dummy_executor,
                user_id="test_p5"
            )
        )
        loop.close()

        self.assertTrue(res.verified)
        self.assertTrue(any(k in res.natural_response.lower() for k in ["directive", "completed", "taken care", "hello", "assist", "request", "ready"]))



    def test_router_integration_with_presence(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(router_manager.route_request("Calculate 125 * 48"))
        loop.close()

        self.assertEqual(res["intent"], "TOOL_EXECUTION")
        self.assertIn("6000", res["response"])
        self.assertEqual(res["formatter_used"], "presence_communication")


if __name__ == "__main__":
    unittest.main()
