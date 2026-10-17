"""Notes and lists: adding, reading, ticking off, and clearing only after a yes. Temporary store only."""
import asyncio
import tempfile
import unittest
from pathlib import Path

from app.tools.executor import ToolExecutor
from app.tools.productivity.notes_tool import NotesStore, NotesTool, list_key
from app.tools.schemas import ToolStatusCode


class NotesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.tool = NotesTool(NotesStore(Path(self.folder.name) / "notes.json"))

    def tearDown(self):
        self.folder.cleanup()

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_list_names(self):
        self.assertEqual(list_key("my Shopping List"), "shopping")
        self.assertEqual(list_key("todo"), "to-do")
        self.assertEqual(list_key(""), "to-do")
        self.assertEqual(list_key("gift ideas"), "gift ideas")

    def test_add_show_and_skip_duplicates(self):
        self.assertEqual(self.run_tool(operation="add_to_list", target="milk", list="shopping", items=["milk", "eggs"])["summary"],
                         "Added milk and eggs to your shopping list.")
        self.assertEqual(self.run_tool(operation="add_to_list", target="Milk", list="shopping list")["summary"],
                         "Milk is already on your shopping list.")
        self.assertEqual(self.run_tool(operation="show_list", target="shopping")["summary"],
                         "Your shopping list:\n1. milk\n2. eggs")

    def test_tick_off_finds_the_list(self):
        self.run_tool(operation="add_to_list", target="2 litres of milk", list="shopping")
        self.assertEqual(self.run_tool(operation="check_off", target="milk")["summary"], "Ticked off 2 litres of milk.")
        self.assertIn("is empty", self.run_tool(operation="show_list", target="shopping")["summary"])

    def test_notes(self):
        self.run_tool(operation="note", target="wifi password is on the fridge")
        self.assertIn("1. wifi password is on the fridge", self.run_tool(operation="show_list", target="notes")["summary"])

    def test_clearing_waits_for_approval(self):
        self.run_tool(operation="add_to_list", target="pay rent")
        proposal = self.run_tool(operation="clear_list", target="to-do")
        self.assertEqual(proposal["summary"], "Clear your to-do list (1 item)?")
        executor = ToolExecutor()
        executor._save_history = lambda: None
        held = asyncio.run(executor.execute_tool(self.tool, {"operation": "remove_list", "target": "to-do"}))
        self.assertEqual(held.status_code, ToolStatusCode.CONFIRMATION_REQUIRED)
        self.assertEqual(len(self.tool.store.items("to-do")), 1)
        self.run_tool(operation="remove_list")
        self.assertEqual(self.tool.store.items("to-do"), [])


if __name__ == "__main__":
    unittest.main()
