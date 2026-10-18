"""Watching an app: finished, text appears, closed, already done, stop. Simulated window and clock."""
import asyncio
import unittest
from unittest.mock import patch

from app.tools.system import watch_tool as watch_module
from app.tools.system.screen_reader import WindowInfo
from app.tools.system.watch_tool import WatchTool

CLAUDE = WindowInfo(hwnd=11, pid=12, title="Claude", process="claude.exe")


class FakeScreen:
    """Successive readings of the window; the last one repeats."""

    def __init__(self, *readings):
        self.readings = list(readings)

    def __call__(self, window):
        return self.readings.pop(0) if len(self.readings) > 1 else self.readings[0]


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.said = []
        self.patches = [
            patch.object(watch_module, "POLL_SECONDS", 0.001),
            patch.object(watch_module, "STILL_SECONDS", 0.05),
            patch.object(watch_module, "IDLE_FROM_START_SECONDS", 0.05),
            patch.object(WatchTool, "_find", staticmethod(lambda target: CLAUDE if target in ("claude", "this") else None)),
            patch("app.tools.system.screen_reader.window_exists", return_value=True),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def run_watch(self, screen, **args):
        tool = WatchTool(reader=screen, notify=lambda text, tone: self.said.append((text, tone)))

        async def scenario():
            result = await tool.execute({"operation": "watch", "target": "claude", **args})
            for watch in list(tool.watches.values()):
                await asyncio.wait_for(watch.task, 5)
            return result
        return asyncio.run(scenario())

    def test_finished_after_activity_stops(self):
        result = self.run_watch(FakeScreen(["thinking"], ["writing 1"], ["writing 2"], ["done answer"]))
        self.assertEqual(result["summary"], "Okay, I'll keep an eye on Claude and tell you when it finishes.")
        self.assertEqual(self.said, [("Claude looks finished. It's stopped changing.", "cheerful")])

    def test_waits_for_named_text(self):
        self.run_watch(FakeScreen(["downloading 10%"], ["downloading 90%"], ["Download complete"]), text="download complete")
        self.assertEqual(self.said, [("Claude now says “download complete”.", "cheerful")])

    def test_never_changing_means_maybe_already_done(self):
        self.run_watch(FakeScreen(["all quiet"]))
        self.assertIn("may already be done", self.said[0][0])

    def test_closed_app(self):
        with patch("app.tools.system.screen_reader.window_exists", return_value=False):
            self.run_watch(FakeScreen(["x"]))
        self.assertEqual(self.said, [("Claude was closed, so I stopped watching it.", "calm")])

    def test_missing_or_unreadable_app(self):
        tool = WatchTool(reader=lambda w: [])
        self.assertIn("don't see figma open", asyncio.run(tool.execute({"operation": "watch", "target": "figma"}))["error"])
        self.assertIn("can't read Claude", asyncio.run(tool.execute({"operation": "watch", "target": "claude"}))["error"])

    def test_stop_watching(self):
        tool = WatchTool(reader=FakeScreen(["a"], ["b"]), notify=lambda t, tone: self.said.append(t))

        async def scenario():
            with patch.object(watch_module, "IDLE_FROM_START_SECONDS", 999), patch.object(watch_module, "STILL_SECONDS", 999):
                await tool.execute({"operation": "watch", "target": "claude"})
                stopped = await tool.execute({"operation": "stop_watching", "target": "all"})
                await asyncio.sleep(0.01)
                return stopped
        self.assertEqual(asyncio.run(scenario())["summary"], "Okay, I stopped watching Claude.")
        self.assertEqual(self.said, [])
        self.assertEqual(tool.watches, {})


if __name__ == "__main__":
    unittest.main()
