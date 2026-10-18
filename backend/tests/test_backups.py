"""The backup chain: a failing service hands over to the next connected one, then this computer."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.cognition.llm import manager
from app.cognition.llm.manager import LLMSettings, RoleProvider


class FakeProvider:
    def __init__(self, name, fails):
        self.name, self.fails = name, fails

    async def generate_response(self, messages, system_prompt, json_mode=False):
        calls.append(self.name)
        if self.name in self.fails:
            return {"response": f"{self.name} failed", "error": True}
        return {"response": f"answer from {self.name}", "provider": self.name}


calls = []


async def _model(service):
    return f"{service}-model"


class BackupChainTests(unittest.TestCase):
    def setUp(self):
        calls.clear()
        manager._failed_at.clear()
        manager._rest_until.clear()
        manager._failures_in_a_row.clear()
        self.folder = tempfile.TemporaryDirectory()
        self.store = LLMSettings(Path(self.folder.name) / "llm.json")
        self.connected = patch.object(manager, "is_connected", side_effect=lambda s: s.id in ("groq", "gemini", "ollama"))
        self.connected.start()
        # Backups check their service's live model list; never ask real services from a test.
        self.models = patch.object(manager, "usable_model", AsyncMock(side_effect=lambda service, role: f"{service}-model"))
        self.models.start()

    def tearDown(self):
        self.models.stop()
        self.connected.stop()
        self.folder.cleanup()

    def ask(self, fails=()):
        with patch.object(manager, "build_provider", side_effect=lambda service, model: FakeProvider(service, fails)):
            return asyncio.run(RoleProvider("conversation", self.store).generate_response([], "sys"))

    def test_order_is_choice_then_connected_cloud_then_this_computer(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        self.assertEqual([c["service"] for c in RoleProvider("conversation", self.store).chain()], ["groq", "gemini", "ollama"])

    def test_chosen_service_answers_when_it_works(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        self.assertEqual(self.ask()["response"], "answer from groq")
        self.assertEqual(calls, ["groq"])

    def test_failure_falls_back_and_says_so(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        result = self.ask(fails={"groq"})
        self.assertEqual((result["response"], result["fallback_from"]), ("answer from gemini", "groq"))
        calls.clear()
        self.ask(fails=set())  # one blip: groq is tried again straight away
        self.assertEqual(calls, ["groq"])
        self.ask(fails={"groq"})
        self.ask(fails={"groq"})  # twice in a row: groq rests for a minute
        calls.clear()
        self.ask(fails=set())
        self.assertEqual(calls, ["gemini"])

    def test_everything_failing_returns_the_last_error(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        result = self.ask(fails={"groq", "gemini", "ollama"})
        self.assertTrue(result["error"])
        self.assertEqual(calls, ["groq", "gemini", "ollama"])

    def test_rate_limited_service_rests_as_long_as_it_asks(self):
        import time
        self.store.set_role("conversation", "groq", "openai/gpt-oss-120b")
        manager.note_failure("groq", retry_after=6 * 3600)
        manager._failed_at["groq"] = time.time() - 120  # the one-minute pause alone would be over
        self.ask()
        self.assertEqual(calls, ["gemini"])

    def test_empty_reply_counts_as_a_failure(self):
        self.store.set_role("conversation", "groq", "openai/gpt-oss-120b")

        class Empty(FakeProvider):
            async def generate_response(self, messages, system_prompt, json_mode=False):
                calls.append(self.name)
                return {"response": ""} if self.name == "groq" else {"response": f"answer from {self.name}"}

        with patch.object(manager, "build_provider", side_effect=lambda service, model: Empty(service, ())):
            result = asyncio.run(RoleProvider("conversation", self.store).generate_response([], "sys"))
        self.assertEqual(result["response"], "answer from gemini")

    def test_short_wait_retries_the_same_service(self):
        self.store.set_role("conversation", "groq", "openai/gpt-oss-120b")
        attempts = []

        class Busy(FakeProvider):
            async def generate_response(self, messages, system_prompt, json_mode=False):
                attempts.append(self.name)
                if self.name == "groq" and attempts.count("groq") == 1:
                    return {"response": "busy", "error": True, "retry_after": 0.01}
                return {"response": f"answer from {self.name}"}

        with patch.object(manager, "build_provider", side_effect=lambda service, model: Busy(service, ())):
            result = asyncio.run(RoleProvider("conversation", self.store).generate_response([], "sys"))
        self.assertEqual((result["response"], attempts), ("answer from groq", ["groq", "groq"]))

    def test_backups_can_be_turned_off(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        self.store.set_backups(False)
        self.assertTrue(self.ask(fails={"groq"})["error"])
        self.assertEqual(calls, ["groq"])
        self.assertEqual(self.store.load()["conversation"]["service"], "groq")  # roles survive the switch


if __name__ == "__main__":
    unittest.main()
