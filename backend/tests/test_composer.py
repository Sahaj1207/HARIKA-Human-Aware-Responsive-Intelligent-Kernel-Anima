"""Rewording action results: facts must survive, and only safe messages are reworded."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.presence import composer


class FakeModel:
    def __init__(self, reply, local=False):
        self.reply, self.local = reply, local

    def is_local(self):
        return self.local

    async def generate_response(self, messages, system_prompt, json_mode=False):
        return {"response": self.reply}


def run(text, reply, local=False):
    with patch("app.cognition.llm.manager.RoleProvider", return_value=FakeModel(reply, local)):
        return asyncio.run(composer.compose(text, "add milk", "warm"))


class ComposerTests(unittest.TestCase):
    def test_warmer_wording_with_facts_kept(self):
        self.assertEqual(run("Added milk and eggs to your shopping list.", "Done! Milk and eggs are on your shopping list."),
                         "Done! Milk and eggs are on your shopping list.")

    def test_changed_numbers_or_names_are_rejected(self):
        self.assertIsNone(run("Battery is at 77%, about 3 hours left.", "Battery's at 70%, a few hours left."))
        self.assertIsNone(run("Sent your email to Priya Sharma.", "Sent your email!"))
        self.assertIsNone(run("Added “Dentist” to your calendar tomorrow at 5 PM.", "Added the dentist visit for tomorrow."))

    def test_only_safe_messages(self):
        self.assertIsNone(run("Send “hi” to Mom on WhatsApp?", "Want me to send hi to Mom?"))  # approvals stay exact
        self.assertIsNone(run("Your shopping list:\n1. milk", "Here you go"))  # lists
        self.assertIsNone(run("Added milk.", "Done, milk added.", local=True))  # local model: no extra seconds

    def test_tone_tag_in_the_rewrite_is_dropped(self):
        self.assertEqual(run("Added milk.", "[cheerful] Done, milk added."), "Done, milk added.")


if __name__ == "__main__":
    unittest.main()
