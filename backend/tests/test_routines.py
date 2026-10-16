"""Routines: creation needs approval, a routine's name runs it, and running reuses ordinary steps.

A fake interpreter stands in for the model and a temporary store for the user's
routines; nothing here executes an action.
"""
import asyncio
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.cognition.core import CognitiveCore
from app.cognition.semantic.contract import ResolvedStep, SemanticRequest
from app.tools.executor import ToolExecutor
from app.tools.productivity import routine_tool as routines
from app.tools.productivity.routine_tool import RoutineStore, RoutineTool, parse_days, routine_due
from app.tools.schemas import ToolStatusCode


def step(operation, target, tool, **parameters):
    return ResolvedStep(operation=operation, target=target, capability=operation, tool_name=tool, parameters=parameters)


class FakeInterpreter:
    def __init__(self, steps, unsupported=None):
        self.steps, self.unsupported, self.seen = steps, unsupported, []

    async def interpret(self, text, context=None, hints=None, timeout=None):
        self.seen.append(text)
        request = SemanticRequest(raw_text=text, probable_goal="x", candidate_capabilities=["x"], confidence=0.9, steps=self.steps)
        if self.unsupported:
            request.clarification_question = f"I understood that you want me to {self.unsupported}, but I don't have a way to do that yet."
            request.validation_error = "No registered capability matched the semantic intent."
        return request


GOOD_NIGHT = [step("mute", "volume", "system_control"), step("remind", "wake up", "reminders", at="07:00")]


class RoutineToolTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = RoutineStore(Path(self.folder.name) / "routines.json")

    def tearDown(self):
        self.folder.cleanup()

    def tool(self, steps=GOOD_NIGHT, unsupported=None):
        self.interpreter = FakeInterpreter(steps, unsupported)
        return RoutineTool(self.store, self.interpreter)

    def run_tool(self, tool, **args):
        return asyncio.run(tool.execute(args))

    def test_create_proposes_and_saves_only_after_approval(self):
        tool = self.tool()
        result = self.run_tool(tool, operation="create_routine", target="good night", steps="mute and remind me to wake up at 7")
        self.assertEqual(self.store.load(), [])
        self.assertEqual(result["confirmation"]["capability"], "save_routine")
        self.assertIn("When you say “good night”, I'll:\n1. mute volume\n2. remind you to wake up", result["summary"])
        self.run_tool(tool, operation="save_routine")
        saved = self.store.get("Good Night")
        self.assertEqual([s["operation"] for s in saved["steps"]], ["mute", "remind"])
        self.assertEqual(saved["steps"][1]["parameters"], {"at": "07:00"})  # times are resolved when it runs

    def test_trigger_matches_what_the_user_says(self):
        tool = self.tool()
        self.run_tool(tool, operation="create_routine", target="good night", steps="mute")
        self.run_tool(tool, operation="save_routine")
        self.assertEqual(self.store.match_trigger("Good night!")["name"], "good night")
        self.assertIsNone(self.store.match_trigger("good night everyone, see you"))
        self.assertEqual(self.store.best_match("my good night routine")["name"], "good night")

    def test_unsupported_step_is_named_and_left_out(self):
        result = self.run_tool(self.tool(unsupported="close everything"), operation="create_routine",
                               target="good night", steps="mute and close everything")
        self.assertIn("I can't close everything yet, so I left it out.", result["summary"])

    def test_scheduled_routine_leaves_out_steps_that_need_approval(self):
        steps = [step("mute", "volume", "system_control"), step("shutdown", "computer", "system_control")]
        tool = self.tool(steps)
        result = self.run_tool(tool, operation="create_routine", target="bedtime",
                               steps="mute and shut down", at="23:30", days="weekdays")
        self.assertIn("every weekday at 11:30 PM", result["summary"])
        self.assertIn("can't include steps that need your OK", result["summary"])
        self.assertEqual([s["operation"] for s in tool.draft.routine["steps"]], ["mute"])

    def test_change_applies_to_the_routine_being_set_up(self):
        tool = self.tool()
        self.run_tool(tool, operation="create_routine", target="good night", steps="mute")
        self.run_tool(tool, operation="create_routine", target="good night", instruction="also open spotify")
        self.assertEqual(self.interpreter.seen[-1], "mute. Then apply this change: also open spotify")

    def test_delete_waits_for_approval(self):
        tool = self.tool()
        self.run_tool(tool, operation="create_routine", target="good night", steps="mute")
        self.run_tool(tool, operation="save_routine")
        proposal = self.run_tool(tool, operation="delete_routine", target="good night routine")
        self.assertEqual(proposal["confirmation"]["capability"], "remove_routine")
        self.assertIsNotNone(self.store.get("good night"))
        self.run_tool(tool, operation="remove_routine")
        self.assertIsNone(self.store.get("good night"))

    def test_executor_refuses_save_and_delete_without_router_confirmation(self):
        tool = self.tool()
        self.run_tool(tool, operation="create_routine", target="good night", steps="mute")
        executor = ToolExecutor()
        executor._save_history = lambda: None
        for operation in ("save_routine", "remove_routine"):
            result = asyncio.run(executor.execute_tool(tool, {"operation": operation, "target": "good night"}))
            self.assertEqual(result.status_code, ToolStatusCode.CONFIRMATION_REQUIRED)
        self.assertEqual(self.store.load(), [])

    def test_unknown_routine_lists_the_real_ones(self):
        self.store.put({"name": "work mode", "steps": [], "schedule": None})
        result = self.run_tool(self.tool(), operation="run_routine", target="party")
        self.assertIn("Your routines are: work mode", result["error"])


class RoutineRunTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = RoutineStore(Path(self.folder.name) / "routines.json")
        self.store.put({"name": "good night", "schedule": None, "steps": [
            {"operation": "remind", "target": "drink water", "parameters": {"at": "07:00"}, "tool_name": "reminders", "label": "x"},
            {"operation": "weather", "target": "here", "parameters": {}, "tool_name": "weather", "label": "y"},
        ]})
        self.patch = patch.object(routines, "routine_store", self.store)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.folder.cleanup()

    def test_routine_expands_into_ordinary_steps(self):
        expanded = CognitiveCore._expand_routines([step("run_routine", "good night", "routines")])
        self.assertEqual([(s.capability, s.target) for s in expanded], [("create_reminder", "drink water"), ("weather", "here")])
        self.assertEqual(expanded[0].parameters, {"at": "07:00"})

    def test_saying_the_name_runs_it_without_the_model(self):
        core = CognitiveCore()
        with patch.object(CognitiveCore, "_interpret_async", side_effect=AssertionError("model consulted")):
            decision = asyncio.run(core.cognize_async("Good night!", user_id="u", session_id="s"))
        self.assertEqual([n.action for n in decision.action_graph.nodes], ["create_reminder", "weather"])

    def test_interpreter_hears_about_saved_routines(self):
        self.assertIn("good night", CognitiveCore()._hints("u", "s")["routines"])


class ScheduleTests(unittest.TestCase):
    def test_days(self):
        self.assertEqual(parse_days("weekdays"), [0, 1, 2, 3, 4])
        self.assertEqual(parse_days("every day"), list(range(7)))
        self.assertEqual(parse_days("monday and friday"), [0, 4])
        self.assertIsNone(parse_days(""))

    def test_due_once_on_its_days(self):
        routine = {"schedule": {"at": "09:00", "days": [0, 1, 2, 3, 4]}, "last_run": ""}
        friday = datetime(2026, 10, 16, 9, 10)
        self.assertTrue(routine_due(routine, friday))
        self.assertFalse(routine_due({**routine, "last_run": "2026-10-16"}, friday))
        self.assertFalse(routine_due(routine, datetime(2026, 10, 17, 9, 10)))  # Saturday
        self.assertFalse(routine_due(routine, friday.replace(hour=8)))
        self.assertFalse(routine_due(routine, friday.replace(hour=10)))  # missed by too long


if __name__ == "__main__":
    unittest.main()


class SmallTalkInsideRequestsTests(unittest.TestCase):
    def test_small_talk_words_inside_a_request_are_confirmed_by_the_interpreter(self):
        from app.router.classifier import intent_classifier
        from app.router.schemas import RequestContext

        core = CognitiveCore(semantic_interpreter_instance=FakeInterpreter([]))  # interpreter available
        for message, deliberate in [("good night", False), ("Thanks!", False), ("good night harika", False),
                                    ("delete the good night routine", True), ("thanks, now open spotify", True)]:
            graph, confidence = intent_classifier.classify_request(RequestContext(message=message))
            self.assertEqual(core.needs_deliberation(graph, confidence), deliberate, message)
