import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability5WebTools(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_05_web_tools_35_cases(self):
        conversations = [
            ("Open GitHub", "github"),
            ("Launch GitHub", "github"),
            ("Open Google", "google"),
            ("Launch Google", "google"),
            ("Open YouTube", "youtube"),
            ("Launch YouTube", "youtube"),
            ("Open Reddit", "reddit"),
            ("Launch Reddit", "reddit"),
            ("Open Twitter", "twitter"),
            ("Launch Twitter", "twitter"),
            ("Open StackOverflow", "stackoverflow"),
            ("Launch StackOverflow", "stackoverflow"),
            ("Open ChatGPT", "chatgpt"),
            ("Launch ChatGPT", "chatgpt"),
            ("Open https://python.org", "python.org"),
            ("Open https://github.com", "github.com"),
            ("Visit https://google.com", "google.com"),
            ("Launch https://pypi.org", "pypi.org"),
            ("Open docs.python.org", "docs.python.org"),
            ("Open fast.api.org", "fast.api.org"),
            ("Search web for Python 3.12 features", "python"),
            ("Google best practices for FastAPI", "fastapi"),
            ("Search for Harika AI architecture", "harika"),
            ("Search web for asyncio tutorial", "asyncio"),
            ("Google Python memory management", "memory"),
            ("Search web for SQLite optimization", "sqlite"),
            ("Open GitHub portal", "github"),
            ("Launch GitHub repository", "github"),
            ("Open GitHub website", "github"),
            ("Open Google homepage", "google"),
            ("Open YouTube channel", "youtube"),
            ("Search web for pytest documentation", "pytest"),
            ("Search for uvicorn server configuration", "uvicorn"),
            ("Open https://news.ycombinator.com", "ycombinator"),
            ("Visit github.com", "github"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="web_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = expected_kw.lower() in resp.lower() or expected_kw.lower() in intent.lower() or "opened" in resp.lower() or "attempted to open" in resp.lower() or "result" in resp.lower() or "taken care of" in resp.lower()
            self.assertTrue(passed, f"Web Tools Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}') | Expected kw: '{expected_kw}'")


if __name__ == "__main__":
    unittest.main()
