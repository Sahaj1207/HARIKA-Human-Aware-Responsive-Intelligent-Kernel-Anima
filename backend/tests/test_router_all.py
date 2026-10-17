import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from app.router.schemas import IntentType, SimulationRequest, RequestContext
from app.router.manager import RouterManager
from app.router.history import RouterHistoryManager
from app.router.metrics import RouterMetricsManager
from tests.live_guard import LIVE, REASON


class TestRouterAllE2E(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.history_file = Path(self.test_dir) / "router_history.json"
        self.history = RouterHistoryManager(storage_file=self.history_file)
        self.metrics = RouterMetricsManager(history_mgr=self.history)
        self.router = RouterManager(history=self.history, metrics=self.metrics)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_e2e_calculator_no_llm(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(self.router.route_request("Calculate 25*18"))
        loop.close()

        self.assertEqual(res["intent"], "TOOL_EXECUTION")
        self.assertIn("450", res["response"])
        self.assertIn(res["formatter_used"], ["direct_tool_result", "presence_communication"])


    @unittest.skipUnless(LIVE, REASON)  # really opens GitHub in the browser
    def test_e2e_open_github_website_tool(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(self.router.route_request("Open GitHub"))
        loop.close()

        self.assertEqual(res["intent"], "TOOL_EXECUTION")
        self.assertTrue(any(k in res["response"].lower() for k in ["github", "done", "completed"]))

    @unittest.skipUnless(LIVE, REASON)  # "remember ..." is confirmed by the real local model
    def test_e2e_memory_store_and_retrieval(self):
        loop = asyncio.new_event_loop()
        store_res = loop.run_until_complete(self.router.route_request("Remember my favourite food is dosa", user_id="e2e_user"))
        self.assertEqual(store_res["intent"], "MEMORY_STORE")

        query_res = loop.run_until_complete(self.router.route_request("What is my favourite food", user_id="e2e_user"))
        loop.close()

        self.assertEqual(query_res["intent"], "MEMORY_QUERY")
        self.assertTrue(any(k in query_res["response"].lower() for k in ["found memory", "remember", "dosa"]))


    def test_e2e_vision_analysis(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(self.router.route_request("Analyse this image"))
        loop.close()

        self.assertEqual(res["intent"], "VISION_ANALYSIS")

    def test_e2e_agent_creation_and_context_continuation(self):
        loop = asyncio.new_event_loop()
        agent_res = loop.run_until_complete(self.router.route_request("Create an agent to test math"))
        self.assertEqual(agent_res["intent"], "AGENT_START")

        # Test context continuation
        ctx = RequestContext(message="Continue", active_agent_id="agent-test-123")
        graph, conf = self.router.classifier.classify_request(ctx)
        loop.close()

        self.assertEqual(graph.nodes[0].intent, IntentType.AGENT_CONTINUE)

    @unittest.skipUnless(LIVE, REASON)  # two-part requests are confirmed by the real local model
    def test_e2e_multi_intent_execution(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(self.router.route_request("Calculate 18*25 and remember the answer"))
        loop.close()

        self.assertIn("450", res["response"])

    def test_e2e_dry_run_simulation(self):
        sim = self.router.simulate_request(SimulationRequest(message="Open GitHub"))
        self.assertEqual(sim.intent, IntentType.TOOL_EXECUTION)
        self.assertFalse(sim.will_execute)
        self.assertIn("Predicted intent", sim.reasoning)


if __name__ == "__main__":
    unittest.main()
