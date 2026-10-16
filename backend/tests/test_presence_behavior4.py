from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager
from app.presence.manager import presence_manager


class TestPresenceBehaviorFixesSprint4(unittest.TestCase):

    def setUp(self):
        presence_manager.state.recent_failures.clear()
        presence_manager.state.current_goal = None

    def test_bug1_and_bug3_multi_intent_hello_open_github(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(router_manager.route_request("hello open github"))
        loop.close()

        self.assertIn("Hello, Sahaj", res["response"])
        self.assertTrue("opened github" in res["response"].lower() or "attempted to open github" in res["response"].lower())
        self.assertNotIn("Here's what I found", res["response"])


    def test_bug3_remember_favourite_drink_then_open_github(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            router_manager.route_request("remember my favourite drink is coffee then open github")
        )
        loop.close()

        self.assertTrue("remember" in res["response"].lower() or "preference" in res["response"].lower())
        self.assertTrue("opened github" in res["response"].lower() or "attempted to open github" in res["response"].lower())

        self.assertNotIn("Here's what I found", res["response"])

    def test_bug3_calculate_and_remember(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            router_manager.route_request("calculate 25*18 and remember it")
        )
        loop.close()

        self.assertIn("450", res["response"])
        self.assertNotIn("Here's what I found", res["response"])

    def test_bug5_social_response_variation(self):
        loop = asyncio.new_event_loop()
        res1 = loop.run_until_complete(router_manager.route_request("How are you?"))
        res2 = loop.run_until_complete(router_manager.route_request("How are you?"))
        loop.close()

        self.assertNotEqual(res1["response"], res2["response"])


if __name__ == "__main__":
    unittest.main()
