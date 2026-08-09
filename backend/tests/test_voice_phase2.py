import unittest
from app.voice.speech_queue import SpeechQueue
from app.voice.speaker import SpeakerCoordinator
from app.voice.conversation import ConversationEngine
from app.voice.schemas import VoiceState


class TestVoicePhase2(unittest.TestCase):

    def setUp(self):
        self.queue = SpeechQueue()
        self.speaker = SpeakerCoordinator(queue_instance=self.queue)
        self.conv = ConversationEngine(timeout_seconds=0.1)

    def test_speech_queue_push_and_pop(self):
        added = self.queue.push_text_chunk("Hello HARIKA. How are you today? I am fine.")
        self.assertEqual(len(added), 3)

        pop1 = self.queue.pop_sentence()
        self.assertEqual(pop1, "Hello HARIKA.")

        self.assertEqual(self.queue.queue_size(), 2)
        self.queue.clear()
        self.assertTrue(self.queue.is_empty())

    def test_speaker_streaming_synthesis(self):
        res = self.speaker.stream_text_response("Processing request. Starting execution now.")
        self.assertIn("queued_sentences", res)
        self.assertEqual(res["current_directive"].get("status"), "ready")

    def test_conversation_engine_turn_and_timeout(self):
        session = self.conv.start_conversation(continuous=True)
        self.assertEqual(session.state, VoiceState.LISTENING)

        self.conv.record_turn("Hello", "Hi there")
        self.assertEqual(session.turn_count, 1)

        import time
        time.sleep(0.15)
        timed_out = self.conv.check_timeout()
        self.assertTrue(timed_out)


if __name__ == "__main__":
    unittest.main()
