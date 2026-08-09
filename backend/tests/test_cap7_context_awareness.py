import asyncio
import unittest
from app.router.manager import router_manager


class TestCapability7ContextAwareness(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def tearDown(self):
        self.loop.close()

    def test_07_context_awareness_35_cases(self):
        conversations = [
            ("What are we talking about?", "discussion"),
            ("What is our current topic?", "topic"),
            ("What were we discussing?", "discussing"),
            ("Recall our context", "context"),
            ("Summarize our conversation", "conversation"),
            ("What did I ask before?", "ask"),
            ("What is my goal right now?", "goal"),
            ("What is the workspace context?", "workspace"),
            ("Where are we?", "context"),
            ("What are we working on?", "working"),
            ("What was my last question?", "question"),
            ("What is the active discussion?", "discussion"),
            ("Summarize current context", "context"),
            ("What was the previous topic?", "topic"),
            ("What are we talking about right now?", "talking"),
            ("What is our focus?", "focus"),
            ("What topic are we on?", "topic"),
            ("Recall current discussion", "discussion"),
            ("What is in my context?", "context"),
            ("What were we talking about earlier?", "talking"),
            ("What is my current task?", "task"),
            ("Summarize active discussion", "discussion"),
            ("What are we doing?", "context"),
            ("What is the current session topic?", "topic"),
            ("What was our last message about?", "message"),
            ("Recall workspace context", "workspace"),
            ("What is the main topic?", "topic"),
            ("What are we working on currently?", "working"),
            ("What is the active context?", "context"),
            ("Summarize the workspace state", "workspace"),
            ("What did we talk about?", "talk"),
            ("What is my active goal?", "goal"),
            ("Where did we leave off?", "context"),
            ("Recall recent conversation", "conversation"),
            ("What are we focusing on?", "focus"),
        ]

        for idx, (prompt, expected_kw) in enumerate(conversations, 1):
            res = self.loop.run_until_complete(router_manager.route_request(prompt, user_id="ctx_user"))
            resp = res.get("response", "")
            intent = res.get("intent", "")
            passed = "clarify" not in resp.lower() and len(resp) > 10 and intent in ["MEMORY_QUERY", "CHAT", "SOCIAL_CONVERSATION", "PLAN_QUERY"]
            self.assertTrue(passed, f"Context Awareness Conversation #{idx} Failed: '{prompt}' -> Response: '{resp}' (Intent: '{intent}')")


if __name__ == "__main__":
    unittest.main()
