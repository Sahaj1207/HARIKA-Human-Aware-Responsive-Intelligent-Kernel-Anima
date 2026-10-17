"""Heads-ups: each kind says its thing once, only when switched on. Fake calendar, people and battery."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.core.battery import Battery
from app.integrations.google.calendar import Event
from app.services.proactive import HeadsUps, ProactiveSettings

NOW = datetime(2026, 10, 19, 9, 50)
CONNECTED = {"calendar": True}


class HeadsUpTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.settings = ProactiveSettings(root / "proactive.json")
        self.heads = HeadsUps(self.settings, root / "state.json")
        standup = Event("e1", "Team standup", NOW + timedelta(minutes=8), NOW + timedelta(minutes=38), location="Room 4")
        later = Event("e2", "Lunch", NOW + timedelta(hours=2), NOW + timedelta(hours=3))
        self.patches = [
            patch("app.integrations.google.account.google_account.status", return_value=CONNECTED),
            patch("app.integrations.google.calendar.google_calendar.events", AsyncMock(return_value=[standup, later])),
            patch("app.tools.productivity.people_tool.people_store.birthdays", return_value=[]),
            patch("app.core.battery.battery_status", return_value=Battery(80, False)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.folder.cleanup()

    def check(self, when=NOW):
        return [item["text"] for item in asyncio.run(self.heads.check(when))]

    def test_meeting_heads_up_once(self):
        self.assertEqual(self.check(), ["Heads up: Team standup starts in 8 minutes at Room 4."])
        self.assertEqual(self.check(NOW + timedelta(minutes=1)), [])  # already told

    def test_meetings_can_be_switched_off(self):
        self.settings.update(meetings=False)
        self.assertEqual(self.check(), [])

    def test_birthday_once_in_the_morning(self):
        priya = {"name": "Priya", "phone": "+919000000001"}
        with patch("app.tools.productivity.people_tool.people_store.birthdays",
                   return_value=[(priya, NOW.date(), None)]):
            self.settings.update(meetings=False)
            self.assertEqual(self.check(NOW.replace(hour=7)), [])  # too early
            self.assertEqual(self.check(), ["It's Priya's birthday today. Want me to send a message?"])
            self.assertEqual(self.check(NOW + timedelta(hours=2)), [])

    def test_low_battery_once_per_discharge(self):
        self.settings.update(meetings=False)
        with patch("app.core.battery.battery_status", return_value=Battery(14, False, 25)):
            self.assertEqual(self.check(), ["Your battery is at 14%, about 25 minutes left. Plug in soon."])
            self.assertEqual(self.check(), [])
        with patch("app.core.battery.battery_status", return_value=Battery(30, True)):
            self.check()  # charged up
        with patch("app.core.battery.battery_status", return_value=Battery(12, False)):
            self.assertEqual(self.check(), ["Your battery is at 12%. Plug in soon."])

    def test_settings_are_clamped(self):
        self.assertEqual(self.settings.update(meeting_minutes=500)["meeting_minutes"], 60)


if __name__ == "__main__":
    unittest.main()
