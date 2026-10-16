from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability1Conversation(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_01_conversation_35_cases(self):
        conversations = [
            ("Who created you?", "Sahaj"),
            ("Who is your creator?", "Sahaj"),
            ("Who built you?", "Sahaj"),
            ("Who made you?", "Sahaj"),
            ("Who developed HARIKA?", "Sahaj"),
            ("Who are you?", "HARIKA"),
            ("What is your name?", "HARIKA"),
            ("Hello", "Hello"),
            ("Hi", "Hi"),
            ("Hey", "Hi"),

            ("Good morning", "morning"),
            ("Good afternoon", "afternoon"),
            ("Good evening", "evening"),
            ("How are you?", "doing well|operational|smoothly|assist"),
            ("How's it going?", "doing well|operational|smoothly|assist"),


            ("What's up?", "tasks"),
            ("Are you okay?", "ready"),
            ("Thanks", "welcome"),

            ("Thank you", "welcome"),
            ("Thanks a lot", "welcome"),
            ("Good night", "night"),
            ("Bye", "later"),
            ("See you", "later"),
            ("What can you do?", "set reminders"),
            ("What are your capabilities?", "set reminders"),
            ("Help", "set reminders"),
            ("What commands do you support?", "set reminders"),
            ("What features do you have?", "set reminders"),
            ("Tell me about yourself", "assistant"),
            ("What else can you do?", "set reminders"),
            ("Hello HARIKA", "Hello"),
            ("Hey assistant", "Hi"),

            ("Are you ready?", "ready"),
            ("Nice to meet you", "meet"),
            ("Can you help me?", "assist|capabilities"),

        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="conv_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            expected_kws = [k.strip().lower() for k in expected_kw.split("|")]
            passed = any(k in resp.lower() or k in intent.lower() for k in expected_kws)
            self.assertTrue(passed, f"Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}') | Expected kw: '{expected_kw}'")



if __name__ == "__main__":
    unittest.main()
