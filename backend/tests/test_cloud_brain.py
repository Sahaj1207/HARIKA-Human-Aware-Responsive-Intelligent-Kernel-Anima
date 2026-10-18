"""Cloud brains: compact instructions and picking models a service still offers. No network."""
import unittest

import app.tools  # noqa: F401  (registers the operations)
from app.cognition.llm.catalog import get_service
from app.cognition.llm.manager import pick_default
from app.cognition.semantic.interpreter import _PROMPT_TEMPLATE, compact_prompt, default_semantic_interpreter


class CompactPromptTests(unittest.TestCase):
    def setUp(self):
        self.operations = default_semantic_interpreter().catalog.describe_operations()

    def test_much_shorter_and_relevant(self):
        full = _PROMPT_TEMPLATE.format(operations=self.operations, context="")
        compact = compact_prompt(self.operations, "", "add bread to my shopping list")
        self.assertLess(len(compact), len(full) * 0.6)
        self.assertIn('"add milk and eggs to my shopping list"', compact)
        self.assertIn('"what is the capital of France?" -> {"actions": []}', compact)  # conversation stays conversation
        self.assertNotIn("{{", compact)

    def test_every_operation_is_still_listed(self):
        compact = compact_prompt(self.operations, "", "tell me a joke")
        for line in self.operations.splitlines():
            self.assertIn(line.split(":", 1)[0], compact)


class ModelPickingTests(unittest.TestCase):
    def test_retired_models_are_replaced_by_the_newest_alternative(self):
        gemini = get_service("gemini")
        offered = ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.6-flash-tts", "gemini-3-flash-preview"]
        self.assertEqual(pick_default(gemini, "conversation", offered), "gemini-3.6-flash")

    def test_speech_and_guard_models_are_never_chosen(self):
        groq = get_service("groq")
        offered = ["allam-2-7b", "whisper-large-v3", "meta-llama/llama-prompt-guard-2-22m", "qwen/qwen3.8-27b"]
        self.assertEqual(pick_default(groq, "conversation", offered), "qwen/qwen3.8-27b")
        self.assertEqual(pick_default(groq, "vision", offered), "")  # never guess that a model can see


if __name__ == "__main__":
    unittest.main()


class ReasoningLeakTests(unittest.TestCase):
    def test_json_answer_left_in_reasoning_is_recovered_but_thinking_is_not(self):
        from app.cognition.llm.providers import _answer_in_reasoning
        self.assertEqual(_answer_in_reasoning('Need to search.{"step": {"skill": "search_web"}}'), '{"step": {"skill": "search_web"}}')
        self.assertEqual(_answer_in_reasoning("The user seems sad; I should be gentle."), "")
        self.assertEqual(_answer_in_reasoning(None), "")
