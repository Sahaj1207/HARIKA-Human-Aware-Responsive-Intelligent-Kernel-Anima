"""Choosing which abilities the cloud model is shown for a message (no AI calls).

The guard test runs every phrase of evals/intents.json through the selection, so a new
feature or example that pushes an ability out of view fails here, not in front of a user.
"""
import asyncio
import json
import os
import unittest
from pathlib import Path

import app.tools  # noqa: F401  (registers the abilities)
from app.cognition.semantic.embedder import Embedder
from app.cognition.semantic.interpreter import (
    _ALWAYS, SemanticInterpreter, compact_prompt, default_semantic_interpreter, prompt_examples,
)
from app.cognition.semantic.selection import CONVERSATION, AbilitySelector, parse_groups

CASES = json.loads((Path(__file__).resolve().parents[1] / "evals" / "intents.json").read_text(encoding="utf-8"))
# The installed app's copy of the meaning model, when this computer has one.
_APP_MODEL = Path(os.environ.get("APPDATA", "")) / "com.harika.desktop" / "models" / "minilm"


def operations() -> str:
    return default_semantic_interpreter().catalog.describe_operations()


def misses(selector: AbilitySelector):
    ops = operations()
    return [(message, op) for message, op, _ in CASES
            if op and op not in selector.select(message, ops, prompt_examples(), _ALWAYS).operations]


class GuardTests(unittest.TestCase):
    def test_words_alone_show_nearly_every_expected_ability(self):
        # Before the meaning model is downloaded, word matching is all there is.
        missed = misses(AbilitySelector(None))
        self.assertLessEqual(len(missed), 2, f"Abilities not shown for: {missed}")

    @unittest.skipUnless((_APP_MODEL / "model_quantized.onnx").exists(), "meaning model not downloaded on this computer")
    def test_with_meaning_every_expected_ability_is_shown(self):
        self.assertEqual(misses(AbilitySelector(Embedder(_APP_MODEL))), [])

    def test_every_ability_has_an_example(self):
        groups = parse_groups(operations(), prompt_examples())
        empty = [g.name for g in groups if not g.examples]
        self.assertEqual(empty, [], "Each ability needs at least one example request in the interpreter prompt")


class SelectionTests(unittest.TestCase):
    def test_shared_operations_teach_every_ability_that_has_them(self):
        groups = parse_groups('- "open", "close": Websites.\n- "open", "close": Apps.\n- "find", "open": Files.',
                              ['"open notepad" -> {{"actions": [{{"operation": "open", "target": "notepad"}}]}}'])
        self.assertEqual([len(g.examples) for g in groups], [1, 1, 1, 0])
        self.assertEqual(groups[-1].name, CONVERSATION)

    def test_rare_words_count_more_than_common_ones(self):
        selection = AbilitySelector(None).select("take a screenshot", operations(), prompt_examples(), _ALWAYS)
        self.assertIn("screenshot", selection.operations)
        prompt = compact_prompt(operations(), "", "take a screenshot", selection)
        self.assertIn('"grab a screenshot of this"', prompt)

    def test_each_part_of_a_request_finds_its_ability(self):
        selection = AbilitySelector(None).select("open chrome, look up F1 news and turn on dark mode",
                                                 operations(), prompt_examples(), _ALWAYS)
        self.assertTrue({"open", "search", "turn_on"} <= selection.operations)


class FakeCloud:
    """Answers the ability pick and the interpretation; records the prompts it was given."""

    def __init__(self, pick):
        self.pick = pick
        self.prompts = []

    def is_local(self):
        return False

    async def generate_response(self, messages, system_prompt, json_mode=False):
        self.prompts.append(system_prompt)
        if "You choose which of HARIKA's abilities" in system_prompt:
            return {"response": json.dumps({"operations": self.pick})}
        return {"response": json.dumps({"actions": [{"operation": "remind", "target": "stretch",
                                                     "parameters": {"in_minutes": 10}}]})}


class FallbackTests(unittest.TestCase):
    def interpret(self, message, pick, confident):
        base = default_semantic_interpreter()
        cloud = FakeCloud(pick)
        interpreter = SemanticInterpreter(cloud, base.catalog)
        original = AbilitySelector.select

        def select(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            result.confident = confident
            return result

        AbilitySelector.select = select
        try:
            request = asyncio.run(interpreter.interpret(message, timeout=5))
        finally:
            AbilitySelector.select = original
        return cloud, request

    def test_unsure_selection_asks_the_model_which_ability_first(self):
        cloud, request = self.interpret("ping me in 10 min to stretch", ["remind", "not_an_operation"], confident=False)
        self.assertEqual(len(cloud.prompts), 2)
        self.assertIn("'timer' for a plain timer", cloud.prompts[1])  # the reminders' full instructions
        self.assertEqual(request.steps[0].operation, "remind")

    def test_sure_selection_needs_one_call(self):
        cloud, _ = self.interpret("remind me to stretch in 10 minutes", ["remind"], confident=True)
        self.assertEqual(len(cloud.prompts), 1)


if __name__ == "__main__":
    unittest.main()
