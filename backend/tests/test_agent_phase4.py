import shutil
import tempfile
import unittest
from pathlib import Path
from app.agents.schemas import AgentStatus, AgentState
from app.agents.history import AgentHistoryManager
from app.agents.metrics import AgentMetricsManager
from app.agents.events import agent_event_bus, AgentEventType


class TestAgentPhase4(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_file = Path(self.test_dir) / "agent_history.json"
        self.history = AgentHistoryManager(storage_file=self.storage_file)
        self.metrics = AgentMetricsManager(history=self.history)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_history_recording_and_persistence(self):
        status = AgentStatus(
            agent_id="agent-999",
            goal_id="goal-999",
            plan_id="plan-999",
            state=AgentState.COMPLETED,
            completed_tasks_count=2
        )

        item = self.history.record_agent_execution(status, "Completed successfully", duration_ms=1500.0)

        self.assertEqual(item.agent_id, "agent-999")
        self.assertEqual(item.tasks_count, 2)

        # Load from disk
        reloaded = AgentHistoryManager(storage_file=self.storage_file)
        records = reloaded.get_history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["agent_id"], "agent-999")

    def test_metrics_calculation(self):
        status = AgentStatus(
            agent_id="agent-888",
            state=AgentState.COMPLETED,
            completed_tasks_count=1
        )
        self.history.record_agent_execution(status, "Task completed successfully", duration_ms=2000.0)

        m = self.metrics.get_metrics()
        self.assertEqual(m.agents_created, 1)
        self.assertEqual(m.completed_count, 1)
        self.assertEqual(m.average_duration_s, 2.0)

    def test_event_bus_emissions(self):
        events = []

        def listener(et, p):
            events.append((et, p))

        for et in AgentEventType:
            agent_event_bus.subscribe(et, listener)

        agent_event_bus.emit(AgentEventType.AGENT_CREATED, {"agent_id": "test-1"})
        agent_event_bus.emit(AgentEventType.AGENT_STARTED, {"agent_id": "test-1"})
        agent_event_bus.emit(AgentEventType.TASK_STARTED, {"agent_id": "test-1"})
        agent_event_bus.emit(AgentEventType.TASK_COMPLETED, {"agent_id": "test-1"})
        agent_event_bus.emit(AgentEventType.AGENT_COMPLETED, {"agent_id": "test-1"})

        self.assertEqual(len(events), 5)


if __name__ == "__main__":
    unittest.main()
