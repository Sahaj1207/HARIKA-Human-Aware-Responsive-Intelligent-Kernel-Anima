"""Replies see the conversation: "ok" after a heads-up, "and tomorrow?" after the weather (no real AI)."""
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from app.cognition.manager import recent_turns
from app.router.action_graph import ActionNode
from app.router.manager import RouterManager
from app.router.resolver import SubsystemResolver
from app.router.schemas import IntentType


class RecentTurnsTests(unittest.TestCase):
    def test_only_real_turns_without_the_current_message(self):
        history = [
            {"sender": "assistant", "role": "assistant", "content": "Your battery is at 15%. Plug in soon."},
            {"sender": "system", "role": "system", "content": "Couldn't reach the engine."},
            {"sender": "user", "role": "user", "content": "  "},
            {"sender": "user", "role": "user", "content": "ok"},  # the app's history ends with the current message
        ]
        self.assertEqual(recent_turns(history, "ok"),
                         [{"role": "assistant", "content": "Your battery is at 15%. Plug in soon."}])

    def test_keeps_the_last_ten(self):
        history = [{"role": "user", "content": f"message {i}"} for i in range(15)]
        turns = recent_turns(history, "new")
        self.assertEqual(len(turns), 10)
        self.assertEqual(turns[-1]["content"], "message 14")


class ChatGetsTheConversationTests(unittest.TestCase):
    def test_resolver_passes_the_conversation_to_the_chat_reply(self):
        node = ActionNode(intent=IntentType.CHAT, engine="CognitionManager", action="process_chat", arguments={"message": "ok"})
        node.conversation_history = [{"role": "assistant", "content": "Your battery is at 15%."}]
        with patch("app.cognition.manager.cognition_manager.process_chat", AsyncMock(return_value={"response": "Good, plug in."})) as chat:
            asyncio.run(SubsystemResolver().execute_node(node, user_id="Sahaj"))
        self.assertEqual(chat.call_args.kwargs["conversation_history"], [{"role": "assistant", "content": "Your battery is at 15%."}])

    def test_conversation_is_kept_out_of_the_logged_arguments(self):
        node = ActionNode(intent=IntentType.CHAT, engine="CognitionManager", arguments={"message": "ok"})
        node.conversation_history = [{"role": "user", "content": "private"}]
        self.assertNotIn("private", repr(node))
        self.assertNotIn("conversation_history", node.arguments)


class RouterTurnsTests(unittest.TestCase):
    def test_heads_up_and_exchanges_are_remembered_for_history_less_requests(self):
        router = RouterManager()
        router.note("assistant", "Your battery is at 15%. Plug in soon.", user_id="Sahaj")
        router.note("user", "what's the weather?", user_id="Sahaj")
        self.assertEqual([t["content"] for t in router.recent_turns("Sahaj")],
                         ["Your battery is at 15%. Plug in soon.", "what's the weather?"])
        self.assertEqual(router.recent_turns("someone else"), [])

    def test_old_turns_are_not_the_conversation(self):
        router = RouterManager()
        router.note("assistant", "Good morning!", user_id="Sahaj")
        router._turns["Sahaj"][0]["time"] = time.time() - 3600
        self.assertEqual(router.recent_turns("Sahaj"), [])

    def test_voice_request_uses_the_remembered_turns(self):
        router = RouterManager()
        router.note("assistant", "Your battery is at 15%. Plug in soon.", user_id="Sahaj")
        seen = {}

        async def cognize(message, **kwargs):
            seen["history"] = kwargs.get("conversation_history")
            raise RuntimeError("stop here")

        router.cognitive_core = type("Core", (), {"cognize_async": staticmethod(cognize)})()
        with self.assertRaises(RuntimeError):
            asyncio.run(router.route_request("okay", user_id="Sahaj", spoken=True))
        self.assertEqual(seen["history"], [{"role": "assistant", "content": "Your battery is at 15%. Plug in soon."}])


if __name__ == "__main__":
    unittest.main()
