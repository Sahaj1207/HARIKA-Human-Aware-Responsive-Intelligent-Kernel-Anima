"""Reminders (parsing, storage, firing) and the live event stream. OS notifications are faked."""
import asyncio
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.core.live_events import LiveEventHub
from app.tools.system.reminders import ReminderStore, RemindersTool, parse_due, run_reminder_scheduler

NOW = datetime(2026, 10, 16, 14, 0, 0)


class ParseDueTests(unittest.TestCase):
    def test_relative_times(self):
        self.assertEqual(parse_due({"in_minutes": 10}, NOW), NOW + timedelta(minutes=10))
        self.assertEqual(parse_due({"in_hours": "1", "in_minutes": 30}, NOW), NOW + timedelta(hours=1, minutes=30))

    def test_clock_times_roll_to_tomorrow_when_past(self):
        self.assertEqual(parse_due({"at": "6pm"}, NOW), NOW.replace(hour=18))
        self.assertEqual(parse_due({"at": "18:30"}, NOW), NOW.replace(hour=18, minute=30))
        self.assertEqual(parse_due({"at": "9 am"}, NOW), (NOW + timedelta(days=1)).replace(hour=9))

    def test_iso_and_invalid(self):
        self.assertEqual(parse_due({"at": "2026-10-17T08:15"}, NOW), datetime(2026, 10, 17, 8, 15))
        self.assertIsNone(parse_due({"at": "whenever"}, NOW))
        self.assertIsNone(parse_due({"in_minutes": 0}, NOW))
        self.assertIsNone(parse_due({}, NOW))


class RemindersToolTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="harika-reminders-")
        self.tool = RemindersTool(ReminderStore(Path(self.dir.name) / "reminders.json"))

    def tearDown(self):
        self.dir.cleanup()

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_create_list_and_cancel(self):
        created = self.run_tool(operation="remind", target="call mom", in_minutes=30)
        self.assertIn("remind you to call mom", created["summary"])
        self.run_tool(operation="remind", target="timer", in_minutes=5)
        listing = self.run_tool(operation="list", target="reminders")
        self.assertEqual([r["text"] for r in listing["reminders"]], ["timer", "call mom"])

        cancelled = self.run_tool(operation="cancel", target="the mom reminder")
        self.assertTrue(cancelled["success"])
        self.assertEqual([r["text"] for r in self.tool.store.pending()], ["timer"])

    def test_cancel_without_match_fails_honestly(self):
        self.run_tool(operation="remind", target="water plants", in_minutes=5)
        result = self.run_tool(operation="cancel", target="dentist")
        self.assertFalse(result["success"])

    def test_reminder_without_time_is_rejected(self):
        self.assertFalse(self.tool.validate({"operation": "remind", "target": "call mom"})[0])

    def test_scheduler_fires_due_reminders_once(self):
        self.tool.store.add("stretch", datetime.now() - timedelta(seconds=1))
        self.tool.store.add("later", datetime.now() + timedelta(hours=1))
        published = []

        async def run_briefly():
            with patch("app.core.live_events.live_events.publish", side_effect=lambda t, **p: published.append((t, p))), \
                 patch("app.tools.system.reminders.show_os_notification") as notify:
                task = asyncio.create_task(run_reminder_scheduler(self.tool, interval_seconds=0.01))
                await asyncio.sleep(0.1)
                task.cancel()
                return notify

        notify = asyncio.run(run_briefly())
        self.assertEqual([p["text"] for _, p in published], ["Reminder: stretch"])
        notify.assert_called_once()
        self.assertEqual([r["text"] for r in self.tool.store.pending()], ["later"])


class LiveEventHubTests(unittest.TestCase):
    def test_subscriber_receives_published_events_as_sse(self):
        hub = LiveEventHub()

        async def scenario():
            stream = hub.stream(heartbeat_seconds=5)
            self.assertEqual(await stream.__anext__(), ": connected\n\n")
            hub.publish("step", index=1, total=2, status="started", label="open chrome")
            frame = await stream.__anext__()
            await stream.aclose()
            return frame

        frame = asyncio.run(scenario())
        self.assertTrue(frame.startswith("event: step\n"))
        payload = json.loads(frame.split("data: ", 1)[1])
        self.assertEqual((payload["label"], payload["status"]), ("open chrome", "started"))

    def test_publish_without_subscribers_is_a_no_op(self):
        LiveEventHub().publish("step", label="nothing listening")


if __name__ == "__main__":
    unittest.main()
