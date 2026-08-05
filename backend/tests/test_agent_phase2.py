import asyncio
import unittest
from app.agents.schemas import AgentState
from app.agents.manager import AgentManager
from app.agents.executor import task_executor
from app.agents.orchestrator import agent_orchestrator
from app.planning.planner import hierarchical_planner
from app.planning.schemas import PlanStep


class TestAgentPhase2(unittest.TestCase):

    def setUp(self):
        self.manager = AgentManager()

    def test_task_executor_calculator_tool(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            task_executor.execute_task(
                task_id="tsk-1",
                step_number=1,
                title="Calculate expression",
                tool_name="calculator",
                arguments={"expression": "15 + 25"}
            )
        )
        loop.close()

        self.assertTrue(res.success)
        self.assertEqual(res.output.get("result"), 40)

    def test_orchestrator_execution(self):
        status = self.manager.create_agent(goal_id="goal-201")
        self.manager.start_agent(status.agent_id)

        steps = [PlanStep(step_number=1, title="Calculate 10 * 10", tool_name="calculator", arguments={"expression": "10 * 10"})]
        plan = hierarchical_planner.create_plan(user_message="Multiply numbers", custom_steps=steps)

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            agent_orchestrator.execute_plan_step(status, plan)
        )
        loop.close()

        self.assertTrue(res.success)
        self.assertEqual(res.output.get("result"), 100)
        self.assertEqual(status.completed_tasks_count, 1)


if __name__ == "__main__":
    unittest.main()
