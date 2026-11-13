"""HARIKA explaining herself, from her records only: how she knew, where it went, what she did."""
import asyncio
import contextvars
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.core import provenance
from app.memory import activity
from app.memory.activity import ActivityLog
from app.tools.utilities.explain import ExplainTool, past_day

TODAY = date(2026, 11, 13)  # a Friday


def notes(abilities=(), ai=(("understanding", "groq", ""),), memories=False):
    return {"abilities": [{"name": n, "uses": u, "sends_to": s} for n, u, s in abilities],
            "ai": [{"role": r, "service": svc, "backup_for": b} for r, svc, b in ai], "memories": memories}


class ProvenanceTests(unittest.TestCase):
    def run_request(self, body):
        return contextvars.copy_context().run(body)

    def test_a_request_keeps_its_notes_with_the_reply(self):
        provenance.recent.clear()

        def request():
            provenance.start()
            provenance.note_ai("conversation", "groq")
            provenance.note_ability("Calendar", "your calendar", "Google")
            provenance.note_ability("Calendar", "your calendar", "Google")  # once is enough
            provenance.note_memories()
            provenance.finish("what's on today?", "Design review at 6.")
        self.run_request(request)
        kept = provenance.last_reply()
        self.assertEqual((kept["reply"], len(kept["abilities"]), kept["memories"]), ("Design review at 6.", 1, True))

    def test_explaining_is_not_kept_and_outside_a_request_nothing_happens(self):
        provenance.recent.clear()

        def request():
            provenance.start()
            provenance.skip()
            provenance.finish("how did you know?", "I looked at your calendar.")
        self.run_request(request)
        self.assertIsNone(provenance.last_reply())
        self.run_request(lambda: provenance.note_ai("conversation", "groq"))  # no request: no error, no notes
        self.assertIsNone(provenance.last_reply())


class HowIKnewTests(unittest.TestCase):
    def test_calendar_through_groq(self):
        text = ExplainTool.how_i_knew(notes([("Calendar", "your calendar", "Google")]))
        self.assertEqual(text, "I looked at your calendar. Your message went to Groq to work it out, and I asked Google. "
                               "Nothing else left your PC.")

    def test_looked_up_online_is_said_first(self):
        text = ExplainTool.how_i_knew(notes([("Weather", "", "the weather service (Open-Meteo)")]))
        self.assertEqual(text, "I looked it up with the weather service (Open-Meteo). Your message went to Groq to work "
                               "it out. Nothing else left your PC.")

    def test_general_knowledge_and_memories(self):
        self.assertTrue(ExplainTool.how_i_knew(notes()).startswith("That came from what I know in general"))
        self.assertIn("what you've told me before", ExplainTool.how_i_knew(notes(memories=True)))

    def test_on_this_pc_only(self):
        text = ExplainTool.how_i_knew(notes([("Notes & lists", "your notes and lists", "")],
                                            ai=(("conversation", "ollama", ""),)))
        self.assertEqual(text, "I looked at your notes and lists. Everything stayed on your PC.")

    def test_a_backup_is_mentioned(self):
        text = ExplainTool.how_i_knew(notes(ai=(("conversation", "gemini", "groq"),)))
        self.assertIn("Groq was busy, so Google Gemini answered", text)

    def test_nothing_answered_yet(self):
        self.assertIn("haven't answered anything yet", ExplainTool.how_i_knew(None))


class WhatIDidTests(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="harika-explain-"))
        self.log = ActivityLog(folder / "activity", folder / "settings.json")
        self.patch = patch.object(activity, "activity_log", self.log)
        self.patch.start()
        at = lambda h, m=0: datetime.combine(TODAY, datetime.min.time()).replace(hour=h, minute=m)
        self.log.add("check the weather in Hyderabad", when=at(8, 51))
        self.log.add("send “Sure, see you at 7!” in WhatsApp to Ananya", activity.SAID_YES, activity.APPROVED,
                     when=at(16, 12))
        self.log.add("shut down the computer", approval=activity.DECLINED, result=activity.NOT_DONE, when=at(17))

    def tearDown(self):
        self.patch.stop()

    def ask(self, day="today", about=""):
        with patch("app.tools.utilities.explain.date") as fake:
            fake.today.return_value = TODAY
            fake.fromisoformat = date.fromisoformat
            return ExplainTool.what_i_did(day, about, today=TODAY)

    def test_the_day_in_order(self):
        text = self.ask()
        self.assertEqual(text, "Here's what I did today: 8:51 AM, check the weather in Hyderabad; 4:12 PM, send “Sure, see "
                               "you at 7!” in WhatsApp to Ananya. You told me not to shut down the computer.")

    def test_did_you(self):
        self.assertEqual(self.ask(about="the reply to Ananya in WhatsApp"),
                         "Yes, I did, at 4:12 PM, after you said yes (send “Sure, see you at 7!” in WhatsApp to Ananya).")
        self.assertTrue(self.ask(about="shut down the computer").startswith("No. At 5:00 PM you told me not to"))
        self.assertEqual(self.ask(about="email to Ravi"), "I don't see that in what I did today.")

    def test_other_days_and_history_off(self):
        self.assertEqual(self.ask("yesterday"), "I didn't do anything for you yesterday.")
        self.log.set_keeping(False)
        self.assertIn("activity history", self.ask())

    def test_past_days(self):
        self.assertEqual(past_day("yesterday", TODAY), date(2026, 11, 12))
        self.assertEqual(past_day("on monday", TODAY), date(2026, 11, 9))
        self.assertEqual(past_day("friday", TODAY), TODAY)
        self.assertIsNone(past_day("whenever", TODAY))


class ToolTests(unittest.TestCase):
    def test_explaining_stays_out_of_activity_and_isnt_kept(self):
        result = asyncio.run(ExplainTool().execute({"operation": "how_i_knew", "target": "last reply"}))
        self.assertTrue(result["not_activity"])
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
