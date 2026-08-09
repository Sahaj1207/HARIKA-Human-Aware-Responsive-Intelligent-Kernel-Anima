import unittest
from app.presence.communication import communication_layer
from app.presence.initiative import initiative_engine
from app.presence.experience import ExperienceDecision
from app.presence.clarification import clarification_engine


class TestPresencePhase4(unittest.TestCase):

    def test_communication_layer_natural_phrasing(self):
        txt1 = communication_layer.format_human_response("MEMORY_STORE", {}, "Remember my favourite food is dosa")
        self.assertEqual(txt1, "I'll remember that.")

        txt2 = communication_layer.format_human_response("TOOL_EXECUTION", {}, "Open GitHub")
        self.assertEqual(txt2, "I've opened GitHub.")



    def test_communication_layer_self_correction(self):
        txt = communication_layer.format_human_response("MEMORY_STORE", {}, "No. I like biryani now")
        self.assertIn("biryani", txt)

    def test_initiative_engine_confidence_threshold(self):
        exp = ExperienceDecision(decision="offer_diagnostics", reason="Build errors")
        init_low = initiative_engine.evaluate_initiative(0.85, exp)
        self.assertIsNone(init_low)

        init_high = initiative_engine.evaluate_initiative(0.95, exp)
        self.assertEqual(init_high, "Offer build log diagnostics")


if __name__ == "__main__":
    unittest.main()
