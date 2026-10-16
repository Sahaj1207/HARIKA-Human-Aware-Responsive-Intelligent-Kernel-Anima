"""Files tool: search ranking, folder targets, and refusing to open programs. No real files are opened."""
import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.tools import recent_results
from app.tools.system.files import FilesTool
from app.tools.web.web_search import WebSearchTool


class FilesToolTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="harika-files-")
        root = Path(self.dir.name)
        now = time.time()
        for name, age in [("Resume_2024.pdf", 50), ("resume screenshot.png", 1), ("resumes-old.docx", 100),
                          ("budget 2024.xlsx", 10), ("install_resume.exe", 0)]:
            path = root / name
            path.write_bytes(b"x")
            os.utime(path, (now - age, now - age))
        self.tool = FilesTool()
        self.roots = patch.object(FilesTool, "search_roots", return_value=[root])
        self.roots.start()
        recent_results.remember("test", [])

    def tearDown(self):
        self.roots.stop()
        self.dir.cleanup()

    def test_exact_document_match_ranks_first(self):
        names = [p.name for p in self.tool.search("resume")]
        self.assertEqual(names[0], "Resume_2024.pdf")
        self.assertIn("resume screenshot.png", names)

    def test_extension_in_query_targets_that_type(self):
        self.assertEqual(self.tool.search("resume png")[0].name, "resume screenshot.png")

    def test_open_never_launches_programs(self):
        exe = Path(self.dir.name) / "install_resume.exe"
        with patch("app.tools.system.files.os.startfile", create=True) as startfile, \
             patch("app.tools.system.files.subprocess.run") as run:
            result = self.tool.open_path(exe, "Opened.")
        startfile.assert_not_called()
        run.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("never programs", result["error"])

    def test_open_best_match_and_remember_list(self):
        with patch.object(FilesTool, "_launch", return_value={"success": True, "verified": True, "summary": "ok"}) as launch:
            asyncio.run(self.tool.execute({"operation": "open", "target": "resume"}))
        self.assertEqual(Path(launch.call_args.args[0]).name, "Resume_2024.pdf")
        self.assertGreater(recent_results.count(), 1)

    def test_find_lists_and_second_one_opens_a_file(self):
        result = asyncio.run(self.tool.execute({"operation": "find", "target": "resume"}))
        self.assertTrue(result["success"])
        self.assertIn("Resume_2024.pdf", result["summary"])
        with patch.object(FilesTool, "_launch", return_value={"success": True, "verified": True}) as launch:
            asyncio.run(WebSearchTool().execute({"operation": "open", "target": "2"}))
        self.assertEqual(Path(launch.call_args.args[0]).name, Path(result["results"][1]).name)

    def test_folder_names_resolve_to_folders_not_searches(self):
        self.assertEqual(self.tool.match_target("my downloads", "open")[0], "downloads")
        self.assertEqual(self.tool.match_target("quarterly report", "open"), ("quarterly report", 0.6))

    def test_partial_match_is_offered_not_opened(self):
        # "note bed" (misheard "notepad") must not open a file that merely contains "note".
        (Path(self.dir.name) / "Python_Notes.zip").write_bytes(b"x")
        with patch.object(FilesTool, "_launch") as launch:
            result = asyncio.run(self.tool.execute({"operation": "open", "target": "note bed"}))
        launch.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("Python_Notes.zip", result["error"])
        self.assertEqual(recent_results.get(0)["title"], "Python_Notes.zip")  # "open the first one" works

    def test_missing_file_fails_honestly(self):
        result = asyncio.run(self.tool.execute({"operation": "open", "target": "blorptastic"}))
        self.assertFalse(result["success"])
        self.assertIn("couldn't find", result["error"])


if __name__ == "__main__":
    unittest.main()
