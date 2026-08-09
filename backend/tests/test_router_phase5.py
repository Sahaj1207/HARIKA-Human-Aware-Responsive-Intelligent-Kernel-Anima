import shutil
import tempfile
import unittest
from pathlib import Path
from app.router.schemas import RoutingDecision, PolicyType
from app.router.history import RouterHistoryManager
from app.router.metrics import RouterMetricsManager


class TestRouterPhase5(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.history_file = Path(self.test_dir) / "router_history.json"
        self.history = RouterHistoryManager(storage_file=self.history_file)
        self.metrics = RouterMetricsManager(history_mgr=self.history)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_history_recording_and_metrics(self):
        decision = RoutingDecision(
            decision_id="dec-100",
            request="Calculate 5+5",
            chosen_engine="ToolManager",
            chosen_action="calculator",
            reason="Arithmetic expression",
            confidence=0.98,
            policy=PolicyType.TOOL_FIRST,
            execution_time_ms=12.5,
            success=True
        )
        self.history.record_decision(decision)

        m = self.metrics.get_metrics()
        self.assertEqual(m.total_requests, 1)
        self.assertIn("ToolManager", m.intent_frequencies)
        self.assertEqual(m.tool_success_rate, 100.0)


if __name__ == "__main__":
    unittest.main()
