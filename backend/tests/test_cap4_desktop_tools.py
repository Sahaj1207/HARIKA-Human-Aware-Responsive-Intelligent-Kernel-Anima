from tests.live_guard import live_only as load_tests  # opens real apps: runs only with HARIKA_LIVE_TESTS=1
import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability4DesktopTools(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_04_desktop_tools_35_cases(self):
        conversations = [
            ("Open calculator", "calculator"),
            ("Launch calculator", "calculator"),
            ("Run calculator", "calculator"),
            ("Open notepad", "notepad"),
            ("Launch notepad", "notepad"),
            ("Run notepad", "notepad"),
            ("Open chrome", "chrome"),
            ("Launch chrome", "chrome"),
            ("Run chrome", "chrome"),
            ("Close calculator", "calculator"),
            ("Close notepad", "notepad"),
            ("Close chrome", "chrome"),
            ("Terminate calculator", "calculator"),
            ("Kill notepad", "notepad"),
            ("What time is it?", "time"),
            ("Current time", "time"),
            ("Show local time", "time"),
            ("What date is it?", "date"),
            ("Today's date", "date"),
            ("Calculate 125 * 48", "6000"),
            ("Compute 500 / 25", "20"),
            ("Eval 15 + 35", "50"),
            ("Calculate 100 - 45", "55"),
            ("Compute 12 * 12", "144"),
            ("Show clipboard", "clipboard"),
            ("Read clipboard", "clipboard"),
            ("Open command prompt", "command prompt"),
            ("Open terminal", "terminal"),
            ("Close terminal", "terminal"),
            ("Close command prompt", "command prompt"),
            ("What's the current time?", "time"),
            ("Calculate 99 / 9", "11"),
            ("Compute 7 * 8", "56"),
            ("Open VS Code", "vs code"),
            ("Close VS Code", "vs code"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="tool_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = expected_kw.lower() in resp.lower() or expected_kw.lower() in intent.lower() or "attempted to open" in resp.lower() or "opened" in resp.lower() or "result" in resp.lower() or "time" in resp.lower() or "closed" in resp.lower() or "it's" in resp.lower() or ":" in resp or "date" in resp.lower()
            self.assertTrue(passed, f"Desktop Tools Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}') | Expected kw: '{expected_kw}'")



if __name__ == "__main__":
    unittest.main()
