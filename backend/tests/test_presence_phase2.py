import unittest
from app.presence.schemas import EntityItem
from app.presence.goal_inference import goal_inference_engine
from app.presence.context_awareness import context_awareness_engine
from app.presence.memory_reasoner import memory_reasoner


class TestPresencePhase2(unittest.TestCase):

    def test_goal_inference(self):
        gi1 = goal_inference_engine.infer_goal("I'm presenting tomorrow morning.")
        self.assertIsNotNone(gi1)
        self.assertIn("Presentation", gi1.inferred_goal)

        gi2 = goal_inference_engine.infer_goal("I keep getting the same build error.")
        self.assertIsNotNone(gi2)
        self.assertIn("Debug", gi2.inferred_goal)

    def test_context_awareness_references(self):
        res1 = context_awareness_engine.resolve_reference("continue")
        self.assertEqual(res1["action"], "continue_task")

    def test_contradiction_resolution(self):
        import uuid
        uid = f"test_u2_{uuid.uuid4().hex[:6]}"
        ent1 = EntityItem(entity="food", attribute="favourite", value="dosa")
        res1 = memory_reasoner.check_and_resolve_contradictions(ent1, user_id=uid)
        self.assertIsNotNone(res1.updated_memory_id)

        ent2 = EntityItem(entity="food", attribute="favourite", value="biryani")
        res2 = memory_reasoner.check_and_resolve_contradictions(ent2, user_id=uid)
        self.assertTrue(res2.has_contradiction)
        self.assertEqual(res2.revision, 2)



if __name__ == "__main__":
    unittest.main()
