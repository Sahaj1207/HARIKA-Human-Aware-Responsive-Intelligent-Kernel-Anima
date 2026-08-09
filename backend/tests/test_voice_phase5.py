import asyncio
import unittest
from app.voice.manager import voice_manager
from app.memory.manager import memory_manager


class TestVoicePhase5(unittest.TestCase):

    def test_voice_directive_tool_and_session_memory(self):
        session = voice_manager.start_session(continuous=True, user_id="test_voice_user")

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            voice_manager.process_voice_directive("eval 100 / 4")
        )
        loop.close()

        self.assertEqual(res["action_type"], "tool")
        self.assertIn("Executed directive", res["response_text"])

        # Stop session & verify session memory summary creation
        stopped_session = voice_manager.stop_session()
        self.assertIsNotNone(stopped_session)

        memories = memory_manager.get_memories(user_id="test_voice_user")
        self.assertTrue(any("Voice Session Summary" in m.title for m in memories))


if __name__ == "__main__":
    unittest.main()
