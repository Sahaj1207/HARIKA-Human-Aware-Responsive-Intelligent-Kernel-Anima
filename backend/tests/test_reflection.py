import unittest
from app.planning.reflection import ReflectionEngine
from app.planning.events import planning_event_bus, PlanningEventType


class TestReflectionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ReflectionEngine()

    def test_reflection_clean_schema_no_chain_of_thought(self):
        events = []
        planning_event_bus.subscribe(PlanningEventType.REFLECTION_STORED, lambda et, p: events.append((et, p)))

        reflection = self.engine.reflect_on_interaction(
            user_message="Find standard python library docs",
            assistant_response="Here are the docs",
            success=True
        )

        dump = reflection.model_dump()

        # Check required fields exist
        self.assertIn("summary", dump)
        self.assertIn("outcome", dump)
        self.assertIn("success", dump)
        self.assertIn("confidence", dump)
        self.assertIn("lessons_learned", dump)
        self.assertIn("next_recommendation", dump)

        # Check NO chain of thought fields exist in schema
        self.assertNotIn("chain_of_thought", dump)
        self.assertNotIn("reasoning", dump)
        self.assertNotIn("scratchpad", dump)
        self.assertNotIn("prompt", dump)

        # Check event emission
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], PlanningEventType.REFLECTION_STORED.value)


if __name__ == "__main__":
    unittest.main()
