import unittest
from app.router.schemas import IntentType
from app.router.confidence import ConfidenceEstimator
from app.router.policy import PolicyEngine
from app.router.formatter import ResponseFormatter


class TestRouterPhase3(unittest.TestCase):

    def setUp(self):
        self.confidence_estimator = ConfidenceEstimator()
        self.policy_engine = PolicyEngine()
        self.formatter = ResponseFormatter()

    def test_confidence_threshold_clarification(self):
        should_clarify, msg = self.confidence_estimator.evaluate(0.45, IntentType.CHAT)
        self.assertTrue(should_clarify)
        self.assertIn("clarification", msg)

        no_clarify, _ = self.confidence_estimator.evaluate(0.95, IntentType.TOOL_EXECUTION)
        self.assertFalse(no_clarify)

    def test_calculator_direct_formatting_without_llm(self):
        result_data = {"status": "success", "result": 450}
        formatted, method = self.formatter.format_response(
            IntentType.TOOL_EXECUTION, result_data, "25 * 18"
        )
        self.assertEqual(formatted, "25 * 18 = 450")
        self.assertEqual(method, "direct_tool_result")

    def test_memory_store_direct_formatting(self):
        formatted, method = self.formatter.format_response(
            IntentType.MEMORY_STORE, {}, "Remember my favourite food is dosa"
        )
        self.assertIn("saved that in your long-term memory", formatted)
        self.assertEqual(method, "direct_memory_stored")


if __name__ == "__main__":
    unittest.main()
