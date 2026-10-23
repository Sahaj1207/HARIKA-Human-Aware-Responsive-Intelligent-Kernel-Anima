"""Tidying Downloads/Desktop: what counts as clutter, asking first, and the Recycle Bin step (faked)."""
import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.tools.system import tidy_tool as tidy
from app.tools.system.tidy_tool import TidyTool, find_clutter

DAY = 86400


class ClutterTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="harika-tidy-"))
        self.now = time.time()

    def make(self, name, data=b"x", age_days=0):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        stamp = self.now - age_days * DAY
        os.utime(path, (stamp, stamp))
        return path

    def test_kinds_of_clutter(self):
        old_installer = self.make("setup-old.exe", b"MZ1", age_days=30)
        self.make("setup-new.exe", b"MZ2", age_days=1)  # fresh: may still be needed
        original = self.make("report.pdf", b"same bytes", age_days=10)
        copy = self.make("report (1).pdf", b"same bytes", age_days=2)
        zipped = self.make("photos.zip", b"PK", age_days=5)
        (self.dir / "photos").mkdir()
        self.make("notes.txt", b"keep me")
        with patch.object(tidy, "_LARGE_BYTES", 50):
            big_old = self.make("movie.mkv", b"v" * 100, age_days=120)
            self.make("new-movie.mkv", b"w" * 100, age_days=3)
            found = find_clutter(self.dir, now=self.now)
        self.assertEqual(found["installers"], [old_installer])
        self.assertEqual(found["duplicates"], [copy])
        self.assertEqual(found["extracted"], [zipped])
        self.assertEqual(found["large"], [big_old])
        self.assertNotIn(original, [p for paths in found.values() for p in paths])

    def test_only_the_kinds_asked_for(self):
        self.make("setup-old.exe", b"MZ", age_days=30)
        self.make("a.txt", b"dup")
        self.make("b.txt", b"dup")
        self.assertEqual(list(find_clutter(self.dir, kinds=["installers"], now=self.now)), ["installers"])

    def test_nothing_deeper_than_two_levels(self):
        self.make("a/b/c/setup.exe", b"MZ", age_days=30)
        self.assertEqual(find_clutter(self.dir, now=self.now), {})


class TidyFlowTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="harika-tidy-"))
        installer = self.dir / "setup.exe"
        installer.write_bytes(b"MZ" * 1000)
        os.utime(installer, (time.time() - 30 * DAY, time.time() - 30 * DAY))
        self.installer = installer
        self.tool = TidyTool()
        self.folder = patch("app.tools.system.files._known_folder", return_value=self.dir)
        self.folder.start()

    def tearDown(self):
        self.folder.stop()

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_reports_then_asks_then_recycles(self):
        report = self.run_tool(operation="tidy", target="downloads")
        self.assertIn("you could free 2 KB: 1 installer (setup.exe)", report["summary"])
        self.assertEqual(report["confirmation"]["capability"], "recycle_clutter")
        self.assertTrue(self.installer.exists())  # nothing moved yet
        with patch.object(tidy, "to_recycle_bin", side_effect=lambda paths: [p.unlink() for p in paths] and len(paths)) as recycle:
            done = self.run_tool(operation="recycle_clutter")
        recycle.assert_called_once_with([self.installer])
        self.assertEqual(done["summary"], "Moved 1 file to the Recycle Bin.")
        self.assertFalse(self.run_tool(operation="recycle_clutter")["success"])  # only once

    def test_tidy_folder_and_stale_yes(self):
        self.installer.unlink()
        self.assertIn("looks tidy", self.run_tool(operation="tidy", target="downloads")["summary"])
        self.tool.pending = ([self.dir / "x"], time.time() - 3600)
        self.assertFalse(self.run_tool(operation="recycle_clutter")["success"])

    def test_recycling_needs_approval(self):
        self.assertEqual(self.tool.manifest.operation_permissions["recycle_clutter"].name, "HIGH")


if __name__ == "__main__":
    unittest.main()
