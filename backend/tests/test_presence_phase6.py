import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestPresencePhase6API(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_get_presence_status_endpoint(self):
        res = self.client.get("/api/v1/presence/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("HARIKA Presence Engine", data["engine"])

    def test_get_presence_state_endpoint(self):
        res = self.client.get("/api/v1/presence/state")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["conversation_mode"], "active")

    def test_get_working_memory_endpoint(self):
        res = self.client.get("/api/v1/presence/working_memory")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), dict)

    def test_get_presence_score_endpoint(self):
        res = self.client.get("/api/v1/presence/score")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("overall_score", data)

    def test_get_presence_metrics_endpoint(self):
        res = self.client.get("/api/v1/presence/metrics")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_observations", data)


if __name__ == "__main__":
    unittest.main()
