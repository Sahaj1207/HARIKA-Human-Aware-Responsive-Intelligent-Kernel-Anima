from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestMemoryRegressionFlow(unittest.TestCase):

    def setUp(self):
        from app.memory.manager import memory_manager
        memory_manager.clear_all_memories("test_flow_user")

    def test_store_retrieve_correct_retrieve(self):
        loop = asyncio.new_event_loop()


        # Step 1: Store
        res1 = loop.run_until_complete(router_manager.route_request("Remember my favourite drink is coffee.", user_id="test_flow_user"))
        self.assertEqual(res1["intent"], "MEMORY_STORE")
        self.assertEqual(res1["response"], "I'll remember that.")

        # Step 2: Retrieve
        res2 = loop.run_until_complete(router_manager.route_request("What's my favourite drink?", user_id="test_flow_user"))
        self.assertEqual(res2["intent"], "MEMORY_QUERY", f"Expected MEMORY_QUERY but got {res2['intent']}")
        self.assertIn("coffee", res2["response"].lower(), f"Expected coffee in response but got: {res2['response']}")

        # Step 3: Correct
        res3 = loop.run_until_complete(router_manager.route_request("No, it's tea.", user_id="test_flow_user"))
        self.assertIn(res3["intent"], ["MEMORY_STORE", "MEMORY_UPDATE"], f"Expected MEMORY_STORE/UPDATE but got {res3['intent']}")
        self.assertIn("tea", res3["response"].lower(), f"Expected tea confirmation but got: {res3['response']}")

        # Step 4: Retrieve again
        res4 = loop.run_until_complete(router_manager.route_request("What's my favourite drink?", user_id="test_flow_user"))
        self.assertEqual(res4["intent"], "MEMORY_QUERY")
        self.assertIn("tea", res4["response"].lower(), f"Expected tea in response but got: {res4['response']}")

        loop.close()


if __name__ == "__main__":
    unittest.main()
