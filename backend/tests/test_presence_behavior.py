from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
import uuid
from app.router.manager import router_manager
from app.presence.manager import presence_manager


class TestPresenceBehaviorFixes(unittest.TestCase):

    def setUp(self):
        presence_manager.state.recent_failures.clear()
        presence_manager.state.current_goal = None

    def test_bug1_greeting_intent(self):
        loop = asyncio.new_event_loop()
        res1 = loop.run_until_complete(router_manager.route_request("Hello"))
        res2 = loop.run_until_complete(router_manager.route_request("Good morning"))
        res3 = loop.run_until_complete(router_manager.route_request("Hi"))
        loop.close()

        self.assertIn("Hello, Sahaj", res1["response"])
        self.assertIn("Good morning", res2["response"])
        self.assertIn("Hi!", res3["response"])

    def test_bug2_tool_output_datetime_and_calculator(self):
        loop = asyncio.new_event_loop()
        res_time = loop.run_until_complete(router_manager.route_request("What time is it?"))
        res_calc = loop.run_until_complete(router_manager.route_request("Calculate 125*48"))
        loop.close()

        self.assertNotEqual(res_time["response"], "Done.")
        self.assertTrue(any(k in res_time["response"].lower() for k in ["it's", "current time", "time"]))

        self.assertNotEqual(res_calc["response"], "Done.")
        self.assertIn("125 * 48 = 6000", res_calc["response"])

    def test_bug3_and_bug7_memory_attribute_isolation(self):
        loop = asyncio.new_event_loop()
        uid = f"user_b3_{uuid.uuid4().hex[:6]}"
        loop.run_until_complete(router_manager.route_request("Remember my favourite drink is coffee", user_id=uid))
        res = loop.run_until_complete(router_manager.route_request("What is my favourite food?", user_id=uid))
        loop.close()

        self.assertNotIn("coffee", res["response"].lower())
        self.assertIn("favourite food", res["response"].lower())

    def test_bug4_correction_handling(self):
        loop = asyncio.new_event_loop()
        uid = f"user_b4_{uuid.uuid4().hex[:6]}"
        loop.run_until_complete(router_manager.route_request("Favourite food is dosa", user_id=uid))
        res_corr = loop.run_until_complete(router_manager.route_request("No. Favourite food is biryani", user_id=uid))
        res_q = loop.run_until_complete(router_manager.route_request("What is my favourite food?", user_id=uid))
        loop.close()

        self.assertIn("biryani", res_corr["response"].lower())
        self.assertIn("biryani", res_q["response"].lower())
        self.assertNotIn("dosa", res_q["response"].lower())

    def test_bug8_full_conversation_flow(self):
        loop = asyncio.new_event_loop()
        uid = f"user_b8_{uuid.uuid4().hex[:6]}"

        # 1. Store food
        res1 = loop.run_until_complete(router_manager.route_request("Remember my favourite food is dosa", user_id=uid))
        self.assertEqual(res1["response"], "I'll remember that.")

        # 2. Query food
        res2 = loop.run_until_complete(router_manager.route_request("What is my favourite food?", user_id=uid))
        self.assertIn("dosa", res2["response"].lower())

        # 3. Store drink
        res3 = loop.run_until_complete(router_manager.route_request("Remember my favourite drink is coffee", user_id=uid))
        self.assertEqual(res3["response"], "I'll remember that.")

        # 4. Query food (verify no coffee pollution)
        res4 = loop.run_until_complete(router_manager.route_request("What is my favourite food?", user_id=uid))
        self.assertIn("dosa", res4["response"].lower())
        self.assertNotIn("coffee", res4["response"].lower())

        loop.close()


if __name__ == "__main__":
    unittest.main()
