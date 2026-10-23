"""Smarter memory: the journal, daily digests, habits and recall (no real AI calls)."""
import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from app.memory.digest import Digester, parse, transcript
from app.memory.journal import Journal
from app.memory.manager import memory_manager
from app.memory.models import MemoryCategory
from app.memory.patterns import Habits, find_habits
from app.tools.productivity.recall_tool import RecallTool, parse_day


def _journal() -> Journal:
    return Journal(Path(tempfile.mkdtemp(prefix="harika-journal-")) / "journal")


def _open(app: str, ok: bool = True):
    return [{"capability": "open_application", "operation": "open", "target": app, "label": f"open {app}", "ok": ok}]


class JournalTests(unittest.TestCase):
    def test_records_and_reads_back_by_day(self):
        j = _journal()
        when = datetime(2026, 10, 20, 9, 30)
        self.assertTrue(j.record("Sahaj", "open spotify", "Opened Spotify.", _open("spotify"), when))
        self.assertEqual(j.days(), [date(2026, 10, 20)])
        entry = j.entries(date(2026, 10, 20))[0]
        self.assertEqual((entry["message"], entry["user"]), ("open spotify", "Sahaj"))
        self.assertEqual(j.owner(), "Sahaj")

    def test_switched_off_keeps_nothing(self):
        j = _journal()
        j.update_settings(remember_conversations=False)
        self.assertFalse(j.record("u", "hello", "hi", []))
        self.assertEqual(j.days(), [])

    def test_search_ranks_by_shared_words(self):
        j = _journal()
        j.record("u", "plan a trip to Goa", "Here's a plan.", [], datetime(2026, 10, 1, 10))
        j.record("u", "what's the weather", "Sunny.", [], datetime(2026, 10, 2, 10))
        j.record("u", "book the Goa trip for December", "Okay.", [], datetime(2026, 10, 3, 10))
        found = j.search("the Goa trips")
        self.assertEqual([e["message"] for e in found], ["book the Goa trip for December", "plan a trip to Goa"])

    def test_prune_and_wipe(self):
        j = _journal()
        j.record("u", "old", "", [], datetime(2026, 1, 1, 10))
        j.record("u", "new", "", [], datetime(2026, 10, 20, 10))
        self.assertEqual(j.prune(today=date(2026, 10, 22)), 1)
        self.assertEqual(j.days(), [date(2026, 10, 20)])
        j.wipe()
        self.assertEqual(j.days(), [])


class DigestTests(unittest.TestCase):
    def setUp(self):
        memory_manager.clear_all_memories(user_id="digest-user")

    def test_parse_tolerates_extra_text(self):
        data = parse('Sure! {"summary": "You planned a trip.", "facts": [{"kind": "plan", "text": "Going to Goa"}, {"text": ""}]}')
        self.assertEqual(data["summary"], "You planned a trip.")
        self.assertEqual(len(data["facts"]), 1)
        self.assertEqual(parse("no json")["summary"], "")

    def test_transcript_marks_who_said_what(self):
        text = transcript([{"time": "2026-10-20T09:30:00", "message": "open spotify", "reply": "Done.",
                            "actions": _open("spotify")}])
        self.assertIn("09:30 You: open spotify", text)
        self.assertIn("HARIKA: Done. [did: open_application]", text)

    def test_digest_saves_summary_and_new_facts_once(self):
        j = _journal()
        day = date(2026, 10, 20)
        j.record("digest-user", "I'm going to Goa on 12 December", "Lovely!", [], datetime(2026, 10, 20, 9))
        seen = {}

        async def ask(prompt, message):
            seen["message"] = message
            return json.dumps({"summary": "You told me about your Goa trip.",
                               "facts": [{"kind": "plan", "text": "Going to Goa on 12 December"},
                                         {"kind": "preference", "text": "Likes beaches"}]})

        digester = Digester(j, ask=ask, state_path=j.folder.parent / "digest_state.json")
        self.assertEqual(digester.pending(today=date(2026, 10, 21)), [day])
        result = asyncio.run(digester.digest(day))
        self.assertEqual(result["facts"], ["Going to Goa on 12 December", "Likes beaches"])
        self.assertIn("<day>", seen["message"])
        items = memory_manager.get_memories(user_id="digest-user")
        episode = [m for m in items if m.category == MemoryCategory.EPISODES]
        self.assertEqual(episode[0].content, "You told me about your Goa trip.")
        self.assertEqual({m.category for m in items if m.category != MemoryCategory.EPISODES},
                         {MemoryCategory.GOALS, MemoryCategory.PREFERENCES})
        self.assertEqual(digester.pending(today=date(2026, 10, 21)), [])
        # Digesting again neither duplicates the day nor the facts it already knows.
        asyncio.run(digester.digest(day))
        self.assertEqual(len(memory_manager.get_memories(user_id="digest-user")), 3)

    def test_no_answer_leaves_the_day_for_later(self):
        j = _journal()
        j.record("digest-user", "hello", "hi", [], datetime(2026, 10, 20, 9))

        async def ask(prompt, message):
            return ""

        digester = Digester(j, ask=ask, state_path=j.folder.parent / "digest_state.json")
        self.assertIsNone(asyncio.run(digester.digest(date(2026, 10, 20))))
        self.assertEqual(digester.pending(today=date(2026, 10, 21)), [date(2026, 10, 20)])


class HabitTests(unittest.TestCase):
    def _entries(self, moments, app="spotify", ok=True):
        return [{"time": m.isoformat(), "message": f"open {app}", "reply": "", "actions": _open(app, ok)} for m in moments]

    def test_daily_habit_needs_five_days_at_a_similar_time(self):
        start = datetime(2026, 10, 5, 9, 0)
        moments = [start + timedelta(days=d, minutes=d * 5) for d in range(5)]
        habits = find_habits(self._entries(moments))
        self.assertEqual(len(habits), 1)
        self.assertIsNone(habits[0]["weekday"])
        self.assertEqual(habits[0]["description"], "Open spotify around 9:10 AM most days")
        self.assertEqual(find_habits(self._entries(moments[:4])), [])

    def test_weekly_habit_and_scattered_times(self):
        mondays = [datetime(2026, 9, 28, 18, 0) + timedelta(weeks=w) for w in range(3)]
        habits = find_habits(self._entries(mondays, app="slack"))
        self.assertEqual([(h["weekday"], h["target"]) for h in habits], [(0, "slack")])
        scattered = [datetime(2026, 10, 1 + d, 7 + 3 * d, 0) for d in range(6)]
        self.assertEqual(find_habits(self._entries(scattered)), [])

    def test_failed_actions_dont_count(self):
        moments = [datetime(2026, 10, 5 + d, 9, 0) for d in range(6)]
        self.assertEqual(find_habits(self._entries(moments, ok=False)), [])

    def test_due_before_usual_time_unless_done_or_dismissed(self):
        j = _journal()
        for d in range(6):
            j.record("u", "open spotify", "", _open("spotify"), datetime(2026, 10, 10 + d, 9, 0))
        habits = Habits(j)
        now = datetime(2026, 10, 20, 8, 52)
        due = habits.due(now)
        self.assertEqual([h["target"] for h in due], ["spotify"])
        self.assertEqual(habits.due(datetime(2026, 10, 20, 8, 30)), [])
        j.record("u", "open spotify", "", _open("spotify"), datetime(2026, 10, 20, 8, 50))
        self.assertEqual(habits.due(now), [])
        habits.dismiss(due[0]["id"])
        self.assertEqual(habits.visible(), [])

    def test_heads_up_respects_the_switch_and_says_it_once(self):
        from app.services.proactive import HeadsUps

        j = _journal()
        habit = {"id": "h1", "label": "open spotify"}
        heads_ups = HeadsUps(state_path=j.folder.parent / "state.json")
        with mock.patch("app.memory.journal.journal", j), \
                mock.patch("app.memory.patterns.habits.due", return_value=[habit]):
            first = heads_ups.habits(datetime(2026, 10, 20, 8, 52))
            self.assertEqual(first[0]["kind"], "habit")
            self.assertIn("You usually open spotify", first[0]["text"])
            self.assertEqual(heads_ups.habits(datetime(2026, 10, 20, 8, 55)), [])
            j.update_settings(notice_habits=False)
            self.assertEqual(heads_ups.habits(datetime(2026, 10, 21, 8, 52)), [])


class RecallTests(unittest.TestCase):
    def test_parse_day(self):
        today = date(2026, 10, 23)  # a Friday
        self.assertEqual(parse_day("yesterday", today), date(2026, 10, 22))
        self.assertEqual(parse_day("the day before yesterday", today), date(2026, 10, 21))
        self.assertEqual(parse_day("Tuesday", today), date(2026, 10, 20))
        self.assertEqual(parse_day("friday", today), date(2026, 10, 16))
        self.assertEqual(parse_day("3 days ago", today), date(2026, 10, 20))
        self.assertEqual(parse_day("2026-10-01", today), date(2026, 10, 1))
        self.assertIsNone(parse_day("the trip", today))

    def test_answers_a_day_from_its_journal(self):
        j = _journal()
        yesterday = datetime.now() - timedelta(days=1)
        j.record("recall-user", "compare laptops under 60k", "The best is the Zenbook.", [], yesterday)
        asked = {}

        async def ask(system, message):
            asked["message"] = message
            return "Yesterday you compared laptops under 60k, and the Zenbook came out best."

        tool = RecallTool(j, ask=ask)
        result = asyncio.run(tool.execute({"target": "everything", "day": "yesterday",
                                           "request": "what did we talk about yesterday?"}))
        self.assertTrue(result["success"])
        self.assertIn("Zenbook", result["summary"])
        self.assertIn("compare laptops under 60k", asked["message"])
        self.assertIn("My question: what did we talk about yesterday?", asked["message"])

    def test_topic_search_and_nothing_found(self):
        j = _journal()
        j.record("recall-user", "let's go to Goa in December", "Sounds fun.", [], datetime.now() - timedelta(days=3))

        async def ask(system, message):
            return "On Monday you decided on Goa in December." if "Goa" in message else ""

        tool = RecallTool(j, ask=ask)
        self.assertIn("Goa", asyncio.run(tool.execute({"target": "the Goa trip"}))["summary"])
        missing = asyncio.run(tool.execute({"target": "the wedding"}))
        self.assertEqual(missing["summary"], "I don't remember us talking about the wedding.")
        empty_day = asyncio.run(tool.execute({"target": "everything", "day": "2026-01-01"}))
        self.assertIn("I don't have anything from", empty_day["summary"])


if __name__ == "__main__":
    unittest.main()
