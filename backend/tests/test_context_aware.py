"""Context-aware HARIKA: meeting offers, quiet hours, moment reminders, follow-through and the wrap-up."""
import asyncio
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.cognition.follow_through import as_follow_up, split_offer
from app.core.battery import Battery
from app.integrations.google.calendar import Event, meeting_url
from app.services.proactive import HeadsUps, ProactiveSettings, quiet
from app.tools.system.reminders import MomentStore, ReminderStore, RemindersTool

NOW = datetime(2026, 10, 19, 9, 50)


class MeetingLinkTests(unittest.TestCase):
    def test_video_link_sources(self):
        self.assertEqual(meeting_url({"hangoutLink": "https://meet.google.com/abc-defg-hij"}), "https://meet.google.com/abc-defg-hij")
        conference = {"conferenceData": {"entryPoints": [{"entryPointType": "phone", "uri": "tel:+1"},
                                                         {"entryPointType": "video", "uri": "https://zoom.us/j/1?pwd=AbC"}]}}
        self.assertEqual(meeting_url(conference), "https://zoom.us/j/1?pwd=AbC")
        self.assertEqual(meeting_url({"location": "Teams: https://teams.microsoft.com/l/meetup/XyZ."}),
                         "https://teams.microsoft.com/l/meetup/XyZ")
        self.assertEqual(meeting_url({"location": "Room 4"}), "")

    def test_website_links_keep_their_case(self):
        from app.tools.system.open_website import OpenWebsiteTool
        result = asyncio.run(OpenWebsiteTool().execute({"target": "https://zoom.us/j/1?pwd=AbC"}, dry_run=True))
        self.assertEqual(result["target_url"], "https://zoom.us/j/1?pwd=AbC")


class HeadsUpContextTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.settings = ProactiveSettings(root / "proactive.json")
        self.heads = HeadsUps(self.settings, root / "state.json")
        self.moments = MomentStore(root / "moments.json")
        call = Event("e1", "Design review", NOW + timedelta(minutes=8), NOW + timedelta(minutes=38),
                     meeting_url="https://meet.google.com/abc-defg-hij")
        self.patches = [
            patch("app.integrations.google.account.google_account.status", return_value={"calendar": True}),
            patch("app.integrations.google.calendar.google_calendar.events", AsyncMock(return_value=[call])),
            patch("app.tools.productivity.people_tool.people_store.birthdays", return_value=[]),
            patch("app.core.battery.battery_status", return_value=Battery(80, False)),
            patch("app.tools.system.reminders.moment_store", self.moments),
            patch("app.core.idle.seconds_idle", return_value=5.0),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.folder.cleanup()

    def test_meeting_with_a_link_offers_to_open_it(self):
        item = asyncio.run(self.heads.check(NOW))[0]
        self.assertEqual(item["text"], "Heads up: Design review starts in 8 minutes. Want me to open the meeting?")
        self.assertEqual(item["offer"]["capability"], "open_website")
        self.assertEqual(item["offer"]["target"], "https://meet.google.com/abc-defg-hij")
        self.assertGreaterEqual(item["offer"]["ttl"], 8 * 60 + 600)

    def test_quiet_hours_keep_only_the_battery(self):
        self.settings.update(quiet_start="09:00", quiet_end="10:00")
        self.assertEqual(asyncio.run(self.heads.check(NOW)), [])
        with patch("app.core.battery.battery_status", return_value=Battery(10, False)):
            self.assertEqual([i["kind"] for i in asyncio.run(self.heads.check(NOW))], ["battery"])

    def test_quiet_hours_across_midnight(self):
        settings = {"quiet_hours": True, "quiet_start": "23:00", "quiet_end": "07:00"}
        self.assertTrue(quiet(settings, NOW.replace(hour=23, minute=30)))
        self.assertTrue(quiet(settings, NOW.replace(hour=6, minute=59)))
        self.assertFalse(quiet(settings, NOW.replace(hour=7, minute=0)))
        self.assertFalse(quiet({**settings, "quiet_hours": False}, NOW.replace(hour=23, minute=30)))

    def test_habit_suggestions_are_capped(self):
        due = [{"id": f"h{i}", "label": f"open app {i}"} for i in range(5)]
        with patch("app.memory.patterns.habits.due", return_value=due):
            self.assertEqual(len(self.heads.habits(NOW, limit=2)), 2)
            self.assertEqual(self.heads.habits(NOW, limit=2), [])  # today's two already said

    def test_welcome_back_after_being_away(self):
        self.settings.update(meetings=False)
        asyncio.run(self.heads.check(NOW))  # HARIKA's first look: nothing waiting yet
        self.moments.add("stretch", "back")
        with patch("app.core.idle.seconds_idle", return_value=900.0):
            self.assertEqual(asyncio.run(self.heads.check(NOW)), [])  # still away
        texts = [i["text"] for i in asyncio.run(self.heads.check(NOW))]
        self.assertEqual(texts, ["Welcome back. You asked me to remind you: stretch."])
        self.assertEqual(asyncio.run(self.heads.check(NOW)), [])

    def test_reminders_from_before_harika_started_come_at_start(self):
        self.settings.update(meetings=False)
        self.moments.add("call the bank", "back", now=time.time() - 3600)
        texts = [i["text"] for i in asyncio.run(self.heads.check(NOW))]
        self.assertEqual(texts, ["Welcome back. You asked me to remind you: call the bank."])


class MomentReminderTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.tool = RemindersTool(ReminderStore(root / "reminders.json"), MomentStore(root / "moments.json"))

    def tearDown(self):
        self.folder.cleanup()

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_person_and_back_reminders(self):
        made = self.run_tool(operation="remind", target="ask Priya about the tickets", person="Priya")
        self.assertEqual(made["summary"], "I'll remind you to ask Priya about the tickets when you talk to Priya.")
        made = self.run_tool(operation="remind", target="drink water", when="back")
        self.assertEqual(made["summary"], "I'll remind you to drink water when you're back at your computer.")
        listing = self.run_tool(operation="list", target="reminders")["summary"]
        self.assertIn("ask Priya about the tickets when you talk to Priya", listing)
        self.assertTrue(self.tool.validate({"operation": "remind", "target": "x", "when": "back"})[0])
        self.assertFalse(self.tool.validate({"operation": "remind", "target": "x"})[0])
        cancelled = self.run_tool(operation="cancel", target="drink water")
        self.assertTrue(cancelled["success"])
        self.assertEqual(len(self.tool.moments.load()), 1)

    def test_mentions_match_whole_names_made_earlier(self):
        store = self.tool.moments
        store.add("ask about the tickets", "person", "Priya", now=100.0)
        self.assertEqual(store.take_mentions(["text Priyanka hi"], before=200.0), [])
        self.assertEqual(store.take_mentions(["I'm messaging Priya now"], before=50.0), [])  # made after this request
        self.assertEqual([r["text"] for r in store.take_mentions(["", "priya"], before=200.0)], ["ask about the tickets"])
        self.assertEqual(store.load(), [])

    def test_router_adds_the_reminder_to_the_reply(self):
        from types import SimpleNamespace
        from app.router.manager import RouterManager

        store = self.tool.moments
        store.add("ask about the tickets", "person", "Priya", now=time.time() - 10)
        node = SimpleNamespace(engine="ToolManager", arguments={"target": "Priya"})
        with patch("app.tools.system.reminders.moment_store", store):
            reply = RouterManager._with_mention_reminders("Sent.", "text her I'm on my way", SimpleNamespace(nodes=[node]), time.time())
        self.assertEqual(reply, "Sent.\n\nBy the way, you asked me to remind you: ask about the tickets.")


class FollowThroughTests(unittest.TestCase):
    def test_offer_note_is_hidden_and_checked(self):
        now = datetime(2026, 10, 23, 20, 0)
        text, offer = split_offer("Good luck with that![offer_reminder: call the bank | 2026-10-26T09:00]", now)
        self.assertEqual(text, "Good luck with that!")
        self.assertEqual(offer, {"task": "call the bank", "at": "2026-10-26T09:00"})
        self.assertIsNone(split_offer("Ok.[offer_reminder: call | 2026-10-01T09:00]", now)[1])  # in the past
        self.assertIsNone(split_offer("Ok.[offer_reminder: call | next week]", now)[1])
        self.assertEqual(split_offer("Plain reply.", now), ("Plain reply.", None))

    def test_offer_becomes_a_held_reminder(self):
        from app.router.manager import RouterManager

        question, follow_up = as_follow_up({"task": "call the bank", "at": "2030-01-07T09:00"})
        self.assertEqual(question, "Want me to remind you on Monday 07 January at 9:00 AM?")
        self.assertEqual((follow_up["capability"], follow_up["operation"], follow_up["parameters"]),
                         ("create_reminder", "remind", {"at": "2030-01-07T09:00"}))
        router = RouterManager()
        reply = router._with_reminder_offer("Good luck!", [{"offer_reminder": {"task": "call the bank", "at": "2030-01-07T09:00"}}],
                                            "u1", "s1")
        self.assertEqual(reply, "Good luck! " + question)
        pending = router._take_pending("u1", "s1")
        self.assertEqual(pending.graph.nodes[0].action, "create_reminder")
        self.assertEqual(pending.graph.nodes[0].arguments["parameters"], {"at": "2030-01-07T09:00"})

    def test_offers_can_stay_open_longer(self):
        from app.router.manager import RouterManager

        router = RouterManager()
        router.offer({"capability": "open_website", "operation": "open", "target": "https://meet.google.com/x",
                      "question": "Should I open it?", "ttl": 900}, user_id="u2")
        router._pending[("u2", "default")].created_at -= 600  # ten minutes later
        self.assertIsNotNone(router._take_pending("u2", "default"))


class WrapUpTests(unittest.TestCase):
    def test_wrap_up_parts(self):
        from app.memory.journal import Journal
        from app.tools.utilities.wrap_up import build_wrap_up, wrap_up_due

        journal = Journal(Path(tempfile.mkdtemp(prefix="harika-journal-")) / "journal")
        now = datetime(2026, 10, 23, 21, 0)
        journal.record("u", "plan a trip to Goa", "Here's a plan.", [], now.replace(hour=10))

        async def ask(prompt, message):
            return "You planned a trip to Goa." if "Goa" in message else ""

        with patch("app.memory.journal.journal", journal), \
                patch("app.integrations.google.account.google_account.status", return_value={"calendar": False}), \
                patch("app.tools.web.weather.locator.resolve", AsyncMock(side_effect=OSError("offline"))), \
                patch("app.tools.utilities.wrap_up.still_open", return_value="Still on your to-do list: milk."), \
                patch("app.tools.utilities.wrap_up.birthdays_tomorrow", return_value="Tomorrow is Priya's birthday."):
            text = asyncio.run(build_wrap_up("Sahaj", now, ask))
        self.assertEqual(text.split("\n\n"), [
            "Here's your day, Sahaj.", "You planned a trip to Goa.", "Still on your to-do list: milk.",
            "Tomorrow is Priya's birthday.", "Sleep well."])
        settings = {"wrap_up_enabled": True, "wrap_up_time": "21:00", "last_wrap_up": ""}
        self.assertTrue(wrap_up_due(settings, now))
        self.assertFalse(wrap_up_due({**settings, "last_wrap_up": "2026-10-23"}, now))
        self.assertFalse(wrap_up_due({**settings, "wrap_up_enabled": False}, now))


if __name__ == "__main__":
    unittest.main()
