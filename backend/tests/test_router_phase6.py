import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestRouterPhase6API(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_get_router_status_endpoint(self):
        response = self.client.get("/api/v1/router")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["engine"], "Cognitive Router v1.0")

    def test_metrics_endpoint(self):
        response = self.client.get("/api/v1/router/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_requests", data)
        self.assertIn("routing_accuracy", data)

    def test_history_endpoint(self):
        response = self.client.get("/api/v1/router/history?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_route_decision_endpoint(self):
        res = self.client.post("/api/v1/router/route", json={"message": "Calculate 25 * 18"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["intent"], "TOOL_EXECUTION")
        self.assertIn("25 * 18 = 450", data["response"])

    def test_simulate_endpoint(self):
        res = self.client.post("/api/v1/router/simulate", json={"message": "Open GitHub"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["intent"], "TOOL_EXECUTION")
        self.assertFalse(data["will_execute"])


if __name__ == "__main__":
    unittest.main()
