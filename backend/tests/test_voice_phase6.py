import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestVoicePhase6API(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_get_voice_status_endpoint(self):
        response = self.client.get("/api/v1/voice")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("speaker", data)
        self.assertIn("transcriber", data)

    def test_metrics_endpoint(self):
        response = self.client.get("/api/v1/voice/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_sessions", data)
        self.assertIn("average_e2e_latency_ms", data)

    def test_history_endpoint(self):
        response = self.client.get("/api/v1/voice/history?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_session_lifecycle_and_interruption_endpoints(self):
        start_res = self.client.post("/api/v1/voice/start", json={"continuous": True})
        self.assertEqual(start_res.status_code, 200)
        self.assertEqual(start_res.json()["status"], "started")

        interrupt_res = self.client.post("/api/v1/voice/interruption")
        self.assertEqual(interrupt_res.status_code, 200)
        self.assertIn("session_id", interrupt_res.json())

        directive_res = self.client.post("/api/v1/voice/directive", json={"voice_text": "eval 5 * 5"})
        self.assertEqual(directive_res.status_code, 200)
        self.assertEqual(directive_res.json()["action_type"], "tool")

        stop_res = self.client.post("/api/v1/voice/stop")
        self.assertEqual(stop_res.status_code, 200)
        self.assertEqual(stop_res.json()["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
