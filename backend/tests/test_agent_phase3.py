import asyncio
import unittest
from app.agents.schemas import AgentState
from app.agents.manager import AgentManager
from app.agents.recovery import RecoveryEngine
from app.agents.monitor import AgentMonitor
from app.agents.scheduler import AgentScheduler


class TestAgentPhase3(unittest.TestCase):

    def setUp(self):
        self.manager = AgentManager()
        self.recovery = RecoveryEngine(max_retries=2)
        self.monitor = AgentMonitor(manager=self.manager)
        self.scheduler = AgentScheduler(manager=self.manager)

    def test_recovery_engine_retries(self):
        loop = asyncio.new_event_loop()
        # Non-existent tool to trigger retries & eventual graceful failure
        res = loop.run_until_complete(
            self.recovery.execute_with_recovery(
                task_id="tsk-fail",
                step_number=1,
                title="Fail Task Test",
                tool_name="non_existent_tool_123"
            )
        )
        loop.close()

        self.assertFalse(res.success)
        self.assertEqual(res.retry_count, 2)
        self.assertIn("Exhausted max retries", res.error)

    def test_monitor_and_scheduler(self):
        status = self.manager.create_agent(goal_id="goal-301")
        self.scheduler.schedule_immediate(status.agent_id)
        self.monitor.record_start(status.agent_id)

        live_status = self.monitor.get_live_status(status.agent_id)
        self.assertIsNotNone(live_status)
        self.assertEqual(live_status.state, AgentState.RUNNING)
        self.assertGreaterEqual(live_status.running_duration_s, 0.0)


if __name__ == "__main__":
    unittest.main()
