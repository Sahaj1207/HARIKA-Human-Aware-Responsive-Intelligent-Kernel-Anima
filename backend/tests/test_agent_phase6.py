import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.agents.manager import agent_manager



class TestAgentPhase6API(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_list_agents_endpoint(self):
        response = self.client.get("/api/v1/agents")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_metrics_endpoint(self):
        response = self.client.get("/api/v1/agents/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("agents_created", data)
        self.assertIn("success_rate_percent", data)

    def test_history_endpoint(self):
        response = self.client.get("/api/v1/agents/history?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_start_and_control_agent_endpoints(self):
        start_res = self.client.post("/api/v1/agents/start", json={"user_message": "Calculate 50 * 2"})
        self.assertEqual(start_res.status_code, 200)
        data = start_res.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("agent_id", data)

        agent_status = agent_manager.create_agent(goal_id="goal-control")
        agent_manager.start_agent(agent_status.agent_id)
        agent_id = agent_status.agent_id

        # Pause agent test
        pause_res = self.client.post("/api/v1/agents/pause", json={"agent_id": agent_id})
        self.assertEqual(pause_res.status_code, 200)
        self.assertEqual(pause_res.json()["state"], "PAUSED")

        # Resume agent test
        resume_res = self.client.post("/api/v1/agents/resume", json={"agent_id": agent_id})
        self.assertEqual(resume_res.status_code, 200)
        self.assertEqual(resume_res.json()["state"], "RUNNING")

        # Cancel agent test
        cancel_res = self.client.post("/api/v1/agents/cancel", json={"agent_id": agent_id})
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["state"], "CANCELLED")



if __name__ == "__main__":
    unittest.main()
