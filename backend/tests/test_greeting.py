"""Greetings and small talk: written for the moment, never repeated, quick when the model can't answer."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.memory.journal import Journal
from app.presence.greeting import Greeter

MORNING = datetime(2026, 10, 24, 8, 30)


def greeter() -> Greeter:
    return Greeter(Path(tempfile.mkdtemp(prefix="harika-greet-")) / "greetings.json")


class GreetingTests(unittest.TestCase):
    def setUp(self):
        self.journal = Journal(Path(tempfile.mkdtemp(prefix="harika-journal-")) / "journal")
        self.patches = [
            patch("app.memory.journal.journal", self.journal),
            patch("app.integrations.google.account.google_account.status", return_value={"calendar": False}),
            patch("app.tools.productivity.people_tool.people_store.birthdays", return_value=[]),
            patch("app.presence.greeting.random.random", return_value=0.9),  # no memory brought up
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_the_model_writes_it_with_the_moment_as_context(self):
        seen = {}

        async def ask(system, message):
            seen["system"], seen["message"] = system, message
            return "[cheerful] Morning, Sahaj! Big day with the dentist at 11?"

        g = greeter()
        self.journal.record("Sahaj", "plan the trip", "ok", [], MORNING - timedelta(days=1))
        reply = asyncio.run(g.reply("good morning", "Sahaj", MORNING, ask))
        self.assertEqual(reply, "[cheerful] Morning, Sahaj! Big day with the dentist at 11?")
        self.assertEqual(seen["message"], "good morning")
        self.assertIn("It's Saturday, morning (8:30 AM).", seen["system"])
        self.assertIn("Their name is Sahaj.", seen["system"])
        self.assertIn("This is the first time you've talked today.", seen["system"])
        self.assertIn("never invent", seen["system"])

    def test_recent_replies_are_passed_on_so_they_are_not_repeated(self):
        replies = iter(["[warm] Hey Sahaj!", "[cheerful] Hi again!"])
        prompts = []

        async def ask(system, message):
            prompts.append(system)
            return next(replies)

        g = greeter()
        asyncio.run(g.reply("hi", "Sahaj", MORNING, ask))
        asyncio.run(g.reply("hello", "Sahaj", MORNING, ask))
        self.assertIn("- (none yet)", prompts[0])
        self.assertIn("- [warm] Hey Sahaj!", prompts[1])
        self.assertEqual(g.recent(), ["[warm] Hey Sahaj!", "[cheerful] Hi again!"])

    def test_quick_greeting_when_the_model_fails_or_is_slow(self):
        async def broken(system, message):
            raise RuntimeError("offline")

        async def slow(system, message):
            await asyncio.sleep(10)
            return "too late"

        g = greeter()
        self.assertIn("morning", asyncio.run(g.reply("hi", "Sahaj", MORNING, broken)).lower())
        with patch("app.presence.greeting._TIMEOUT", 0.05):
            self.assertNotEqual(asyncio.run(g.reply("hi", "Sahaj", MORNING, slow)), "too late")

    def test_quick_greetings_fit_the_hour_and_avoid_the_last_one(self):
        g = greeter()
        first = g.quick("hi", "Sahaj", MORNING)
        g._remember(first)
        self.assertNotEqual(g.quick("hi", "Sahaj", MORNING), first)
        late = g.quick("hello", "", MORNING.replace(hour=2)).lower()
        self.assertTrue("still up" in late or "it's late" in late, late)
        self.assertTrue(g.quick("how are you?", "", MORNING).endswith("?"))  # answers, then asks back

    def test_local_model_uses_the_quick_greeting(self):
        class Local:
            def __init__(self, role):
                pass

            def is_local(self):
                return True

        g = greeter()
        with patch("app.cognition.llm.manager.RoleProvider", Local):
            self.assertIn("morning", asyncio.run(g.reply("hi", "Sahaj", MORNING)).lower())

    def test_what_is_coming_up_today(self):
        from app.tools.system.reminders import reminders_tool
        due = MORNING.replace(hour=11, minute=0)
        with patch.object(reminders_tool.store, "pending", return_value=[{"text": "dentist", "due": due.isoformat()}]):
            lines = asyncio.run(greeter().context("Sahaj", MORNING))
        self.assertIn("Their next reminder today: dentist at 11:00 AM.", lines)


class RoutingTests(unittest.TestCase):
    def test_greeting_reply_is_used_as_written(self):
        from app.presence.communication.chat import format_chat_response
        reply = format_chat_response("CHAT", {"message": "hi", "response": "[warm] Hey Sahaj! Coffee time?", "small_talk": True})
        self.assertEqual(reply, "[warm] Hey Sahaj! Coffee time?")


if __name__ == "__main__":
    unittest.main()
