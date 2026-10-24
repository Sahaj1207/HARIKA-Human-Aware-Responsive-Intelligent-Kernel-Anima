"""Reading notifications: phone (Phone Link) vs everything, filtering by person/app, access problems (faked)."""
import asyncio
import unittest
from datetime import datetime, timedelta, timezone

from app.tools.system.notifications_tool import Notice, NotificationsTool

NOW = datetime.now(timezone.utc)
PHONE_ID = "Microsoft.YourPhone_8wekyb3d8bbwe!App"


def notices():
    return [
        Notice("Phone Link", PHONE_ID, ["Mom", "Call me when you're free"], NOW - timedelta(minutes=5)),
        Notice("Phone Link", PHONE_ID, ["WhatsApp: Priya", "See you at 7!"], NOW - timedelta(hours=2)),
        Notice("Outlook", "Microsoft.Outlook", ["Ravi Kumar", "Report attached"], NOW - timedelta(minutes=30)),
    ]


def tool_with(items, problem=""):
    async def reader():
        return (items, problem) if items is not None else (None, problem)
    return NotificationsTool(reader)


def run(tool, **args):
    return asyncio.run(tool.execute(args))


class NotificationTests(unittest.TestCase):
    def test_phone_messages_only(self):
        result = run(tool_with(notices()), operation="notifications", target="phone")
        self.assertEqual(result["summary"].splitlines(), [
            "2 notifications on your phone:",
            "- Mom: Call me when you're free (5 min ago)",
            "- WhatsApp: Priya: See you at 7! (2 h ago)",
        ])

    def test_everything_names_the_app(self):
        lines = run(tool_with(notices()), operation="notifications", target="all")["summary"].splitlines()
        self.assertEqual(lines[0], "3 notifications:")
        self.assertIn("- Outlook: Ravi Kumar: Report attached (30 min ago)", lines)

    def test_filter_by_person_or_app(self):
        tool = tool_with(notices())
        self.assertIn("Call me", run(tool, operation="notifications", target="Mom", phone=True)["summary"])
        self.assertIn("See you at 7", run(tool, operation="notifications", target="whatsapp")["summary"])
        self.assertEqual(run(tool, operation="notifications", target="Arjun")["summary"], "No notifications from Arjun.")

    def test_no_linked_phone_explains_phone_link(self):
        others = [n for n in notices() if not n.from_phone]
        summary = run(tool_with(others), operation="notifications", target="phone")["summary"]
        self.assertIn("open Phone Link", summary)

    def test_access_denied_says_where_to_allow_it(self):
        result = run(tool_with(None, "Windows isn't letting me read notifications. Turn it on in ..."), operation="notifications")
        self.assertFalse(result["success"])
        self.assertIn("Windows isn't letting me", result["error"])


if __name__ == "__main__":
    unittest.main()


class NativeOrderTests(unittest.TestCase):
    def test_reading_notifications_first_never_crashes_the_meaning_model(self):
        """WinRT loaded before onnxruntime crashes Python; the notification reader prevents it."""
        import platform
        import subprocess
        import sys
        if platform.system() != "Windows":
            self.skipTest("Windows only")
        code = ("import asyncio\n"
                "from app.tools.system.notifications_tool import read_notices\n"
                "asyncio.run(read_notices())\n"
                "import onnxruntime\n"
                "print('ok')\n")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn("ok", result.stdout)
