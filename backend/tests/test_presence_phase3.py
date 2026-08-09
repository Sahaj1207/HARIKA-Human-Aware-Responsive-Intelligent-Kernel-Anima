import unittest
from app.presence.reflection import reflection_engine
from app.presence.verification import verification_engine
from app.presence.experience import experience_engine


class TestPresencePhase3(unittest.TestCase):

    def test_reflection_engine(self):
        res = reflection_engine.reflect_on_execution("TOOL_EXECUTION", {"status": "success", "result": 450}, "25 * 18")
        self.assertTrue(res.answered_user_question)

    def test_verification_engine(self):
        ver = verification_engine.verify_output("ToolManager", {"status": "success"})
        self.assertTrue(ver.overall_valid)

    def test_experience_engine_diagnostics(self):
        ver = verification_engine.verify_output("ToolManager", {"status": "success"})
        exp = experience_engine.evaluate_experience(ver, "I keep getting a build error", recent_failures=["f1", "f2"])
        self.assertEqual(exp.decision, "offer_diagnostics")


if __name__ == "__main__":
    unittest.main()
