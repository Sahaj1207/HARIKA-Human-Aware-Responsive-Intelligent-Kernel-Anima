import unittest
from app.planning.schemas import DecisionStrategy
from app.planning.decision_engine import DecisionEngine
from app.planning.events import planning_event_bus, PlanningEventType


class TestDecisionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = DecisionEngine(confidence_threshold=0.70)

    def test_high_confidence_decision(self):
        events = []
        planning_event_bus.subscribe(PlanningEventType.DECISION_MADE, lambda et, p: events.append((et, p)))

        decision = self.engine.evaluate_decision("Please remember my favourite color is blue")
        self.assertEqual(decision.strategy, DecisionStrategy.RETRIEVE_MEMORY)
        self.assertGreaterEqual(decision.confidence, 0.70)
        self.assertTrue(len(events) > 0)

    def test_low_confidence_forced_clarification_no_guessing(self):
        # Even if a tool action is passed, if override_confidence is below threshold (0.50 < 0.70), ask clarification
        decision = self.engine.evaluate_decision(
            "Do something",
            is_tool_action=True,
            tool_name="unclear_tool",
            override_confidence=0.50
        )
        self.assertEqual(decision.strategy, DecisionStrategy.ASK_CLARIFICATION)
        self.assertIsNone(decision.selected_tool)  # Never guess
        self.assertIn("below threshold", decision.reason)

    def test_ambiguous_short_directive(self):
        decision = self.engine.evaluate_decision("x")
        self.assertEqual(decision.strategy, DecisionStrategy.ASK_CLARIFICATION)
        self.assertLess(decision.confidence, 0.70)


if __name__ == "__main__":
    unittest.main()
