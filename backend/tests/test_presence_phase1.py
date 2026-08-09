import unittest
from app.presence.schemas import AttentionLevel
from app.presence.workspace import workspace_manager
from app.presence.attention import attention_model
from app.presence.presence_score import presence_score_calculator
from app.presence.presence_loop import presence_loop
from app.presence.entity_extractor import entity_extractor


class TestPresencePhase1(unittest.TestCase):

    def test_workspace_manager(self):
        workspace_manager.set_item("current_project", "HARIKA OS")
        self.assertEqual(workspace_manager.get_item("current_project"), "HARIKA OS")

    def test_attention_model(self):
        att1 = attention_model.evaluate_attention("Check status", active_agent_id="agent-123")
        self.assertEqual(att1.level, AttentionLevel.HIGHEST)

        att2 = attention_model.evaluate_attention("Repeated build error in compiler")
        self.assertEqual(att2.level, AttentionLevel.HIGH)

    def test_presence_score(self):
        score = presence_score_calculator.calculate_score()
        self.assertGreaterEqual(score.overall_score, 90.0)

    def test_presence_loop_observation(self):
        decision = presence_loop.observe_state()
        self.assertEqual(decision, "observe_only")

    def test_entity_extractor(self):
        item = entity_extractor.extract_entity("My favourite food is dosa.")
        self.assertIsNotNone(item)
        self.assertEqual(item.entity, "user")
        self.assertEqual(item.attribute, "favourite_food")
        self.assertEqual(item.value, "dosa")



if __name__ == "__main__":
    unittest.main()
