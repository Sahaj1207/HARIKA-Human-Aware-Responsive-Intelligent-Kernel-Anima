from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability6EmotionalSupport(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_06_emotional_support_35_cases(self):
        conversations = [
            ("I'm stressed", "here for you"),
            ("I feel overwhelmed today", "overwhelmed"),
            ("I'm anxious about my exam", "breath"),
            ("I'm feeling down", "here"),
            ("I feel exhausted", "take a break"),
            ("I'm having a bad day", "sorry to hear"),
            ("I'm feeling tired", "rest"),
            ("I feel frustrated", "understand"),
            ("I am stressed out", "breathe"),
            ("I feel hopeless", "support"),
            ("I'm feeling sad today", "hear that"),
            ("I feel burnt out", "pause"),
            ("I'm feeling nervous", "calm"),
            ("I feel stressed with work", "take it step by step"),
            ("I'm feeling lonely", "here"),
            ("I feel exhausted from studying", "break"),
            ("I'm feeling demotivated", "one step"),
            ("I feel stressed about deadlines", "focus"),
            ("I'm feeling worried", "help"),
            ("I feel upset", "understand"),
            ("I'm feeling stressed", "support"),
            ("I feel overwhelmed with tasks", "help"),
            ("I'm feeling anxious", "steady"),
            ("I feel low today", "gentle"),
            ("I'm feeling stressed out", "listen"),
            ("I feel tired of errors", "debug together"),
            ("I'm feeling overwhelmed", "step"),
            ("I feel sad", "here"),
            ("I'm feeling down today", "care"),
            ("I feel anxious", "breath"),
            ("I'm stressed with bug fixes", "tackle together"),
            ("I feel exhausted today", "rest"),
            ("I'm feeling stressed about project", "plan"),
            ("I feel overwhelmed", "here"),
            ("I'm feeling bad today", "listen"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="emo_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = intent in ["SOCIAL_CONVERSATION", "CHAT"] and "clarify" not in resp.lower() and len(resp) > 10
            self.assertTrue(passed, f"Emotional Support Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}')")


if __name__ == "__main__":
    unittest.main()
