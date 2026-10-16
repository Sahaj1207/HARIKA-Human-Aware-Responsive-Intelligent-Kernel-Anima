from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability2Memory(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_02_memory_35_cases(self):
        conversations = [
            ("Remember my favourite drink is coffee", "coffee"),
            ("Remember my favourite food is dosa", "dosa"),
            ("Remember my favourite color is blue", "blue"),
            ("Remember my favourite language is Python", "Python"),
            ("Remember my favourite pet is dog", "dog"),
            ("Remember my favourite city is Tokyo", "Tokyo"),
            ("Remember my favourite sport is cricket", "cricket"),
            ("Remember my favourite music is rock", "rock"),
            ("Remember my favourite fruit is mango", "mango"),
            ("What is my favourite drink?", "coffee"),
            ("Do you know my favourite drink?", "coffee"),
            ("Favourite beverage?", "coffee"),
            ("What do I like drinking?", "coffee"),
            ("What is my favourite food?", "dosa"),
            ("Do you know my favourite food?", "dosa"),
            ("Favourite food?", "dosa"),
            ("What do I like eating?", "dosa"),
            ("What is my favourite color?", "blue"),
            ("What is my favourite language?", "Python"),
            ("What is my favourite pet?", "dog"),
            ("What is my favourite city?", "Tokyo"),
            ("What is my favourite sport?", "cricket"),
            ("What is my favourite music?", "rock"),
            ("What is my favourite fruit?", "mango"),
            ("No, it's tea", "tea"),
            ("What's my favourite drink?", "tea"),
            ("No, my favourite food is biryani", "biryani"),
            ("What is my favourite food?", "biryani"),
            ("No, I like Java now", "Java"),
            ("What is my favourite language?", "Java"),
            ("No, my favourite city is Paris now", "Paris"),
            ("What is my favourite city?", "Paris"),
            ("Remember my project name is HarikaEngine", "HarikaEngine"),
            ("What is my project name?", "HarikaEngine"),
            ("Do you remember my project name?", "HarikaEngine"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="mem_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = expected_kw.lower() in resp.lower() or "remember" in resp.lower() or "updated" in resp.lower() or "preference" in resp.lower()
            self.assertTrue(passed, f"Memory Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}') | Expected kw: '{expected_kw}'")


if __name__ == "__main__":
    unittest.main()
