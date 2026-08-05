import asyncio
import unittest
from app.agents.manager import agent_manager
from app.memory.manager import memory_manager


class TestAgentPhase5(unittest.TestCase):

    def test_full_cross_engine_integration(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            agent_manager.execute_agent_goal(
                user_message="Calculate sqrt(144) + 12",
                user_id="test_agent_user"
            )
        )
        loop.close()

        self.assertEqual(res["status"], "COMPLETED")
        self.assertIsNotNone(res["agent_id"])
        self.assertEqual(res["task_result"]["output"]["result"], 24.0)

        # Check memory integration
        memories = memory_manager.get_memories(user_id="test_agent_user")
        self.assertTrue(any("Completed Agent Goal" in m.title for m in memories))


if __name__ == "__main__":
    unittest.main()
