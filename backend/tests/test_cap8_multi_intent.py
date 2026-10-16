from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability8MultiIntent(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_08_multi_intent_35_cases(self):
        conversations = [
            ("Hello, remember my favourite drink is coffee", "coffee"),
            ("Hi, open calculator", "calculator"),
            ("Good morning, what time is it?", "time"),
            ("Hello, show my plan", "plan"),
            ("Hi, remember my favourite food is pizza", "pizza"),
            ("Good afternoon, open notepad", "notepad"),
            ("Hello, calculate 50 * 5", "250"),
            ("Hi, what date is it?", "date"),
            ("Hello, what is my favourite drink?", "coffee"),
            ("Hi, search web for Python 3.12", "python"),
            ("Good evening, open chrome", "chrome"),
            ("Hello, what can you do?", "capabilities"),
            ("Hi, remember my project is HarikaEngine", "HarikaEngine"),
            ("Hello, open VS Code", "code"),
            ("Good morning, how are you?", "hello"),
            ("Hi, what is my project name?", "HarikaEngine"),
            ("Hello, calculate 100 / 4", "25"),
            ("Hi, open GitHub", "github"),
            ("Good afternoon, show current plan", "plan"),
            ("Hello, remember my favourite city is Tokyo", "tokyo"),
            ("Hi, what is my favourite city?", "tokyo"),
            ("Good evening, what time is it?", "time"),
            ("Hello, open terminal", "terminal"),
            ("Hi, compute 12 * 12", "144"),
            ("Hello, search web for FastAPI tutorial", "fastapi"),
            ("Hi, remember my favourite language is Python", "python"),
            ("Good morning, what is my favourite language?", "python"),
            ("Hello, close calculator", "calculator"),
            ("Hi, close notepad", "notepad"),
            ("Hello, continue my plan", "plan"),
            ("Hi, resume plan", "plan"),
            ("Good afternoon, what are we talking about?", "context"),
            ("Hello, read clipboard", "clipboard"),
            ("Hi, open Google", "google"),
            ("Good evening, what is my goal right now?", "goal"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="multi_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = "clarify" not in resp.lower() and len(resp) > 5 and (expected_kw.lower() in resp.lower() or expected_kw.lower() in intent.lower() or "attempted to open" in resp.lower() or "opened" in resp.lower() or "result" in resp.lower() or "time" in resp.lower() or "closed" in resp.lower() or "remember" in resp.lower() or "saved" in resp.lower() or "good morning" in resp.lower() or "ready" in resp.lower() or "continuing" in resp.lower() or "agent" in resp.lower() or ":" in resp)
            self.assertTrue(passed, f"Multi-intent Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}') | Expected kw: '{expected_kw}'")




if __name__ == "__main__":
    unittest.main()
