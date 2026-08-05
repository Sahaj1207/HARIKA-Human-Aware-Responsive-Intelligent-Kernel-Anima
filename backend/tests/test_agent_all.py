import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from app.agents.schemas import AgentState, AgentStatus
from app.agents.state_machine import AgentStateMachine, InvalidAgentStateTransitionError
from app.agents.manager import AgentManager
from app.agents.history import AgentHistoryManager
from app.agents.metrics import AgentMetricsManager
from app.agents.recovery import RecoveryEngine
from app.agents.events import agent_event_bus, AgentEventType


class TestAgentAllE2E(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.history_file = Path(self.test_dir) / "agent_history.json"
        self.history = AgentHistoryManager(storage_file=self.history_file)
        self.metrics = AgentMetricsManager(history=self.history)
        self.manager = AgentManager()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_e2e_agent_lifecycle(self):
        status = self.manager.create_agent(goal_id="goal-e2e-1")
        self.assertEqual(status.state, AgentState.READY)

        self.manager.start_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.RUNNING)

        self.manager.pause_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.PAUSED)

        self.manager.resume_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.RUNNING)

        self.manager.cancel_agent(status.agent_id)
        self.assertEqual(status.state, AgentState.CANCELLED)

    def test_e2e_full_goal_execution_and_metrics(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            self.manager.execute_agent_goal(user_message="eval 25 * 4", user_id="e2e_user")
        )
        loop.close()

        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["task_result"]["output"]["result"], 100)

    def test_e2e_recovery_on_failed_tool(self):
        recovery = RecoveryEngine(max_retries=1)
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            recovery.execute_with_recovery(
                task_id="tsk-e2e-fail",
                step_number=1,
                title="Unknown tool step",
                tool_name="non_existent_tool_xyz"
            )
        )
        loop.close()

        self.assertFalse(res.success)
        self.assertIn("Exhausted max retries", res.error)


if __name__ == "__main__":
    unittest.main()
