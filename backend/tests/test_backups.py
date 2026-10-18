"""The backup chain: a failing service hands over to the next connected one, then this computer."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.folder = tempfile.TemporaryDirectory()
        self.store = LLMSettings(Path(self.folder.name) / "llm.json")
        self.connected = patch.object(manager, "is_connected", side_effect=lambda s: s.id in ("groq", "gemini", "ollama"))
        self.connected.start()
        # Backups check their service's live model list; never ask real services from a test.
        self.models = patch.object(manager, "usable_model", side_effect=lambda service, role: _model(service))
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
        self.ask(fails=set())  # groq is cooling down for a minute
        self.assertEqual(calls, ["gemini"])

    def test_everything_failing_returns_the_last_error(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        result = self.ask(fails={"groq", "gemini", "ollama"})
        self.assertTrue(result["error"])
        self.assertEqual(calls, ["groq", "gemini", "ollama"])

    def test_backups_can_be_turned_off(self):
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        self.store.set_backups(False)
        self.assertTrue(self.ask(fails={"groq"})["error"])
        self.assertEqual(calls, ["groq"])
        self.assertEqual(self.store.load()["conversation"]["service"], "groq")  # roles survive the switch


if __name__ == "__main__":
    unittest.main()
