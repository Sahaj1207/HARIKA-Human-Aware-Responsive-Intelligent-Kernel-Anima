import unittest
from app.voice.schemas import VoiceState
from app.voice.manager import VoiceManager
from app.voice.speech_queue import SpeechQueue
from app.voice.interrupt import InterruptionEngine
from app.voice.wakeword import WakeWordEngine


class TestVoicePhase3(unittest.TestCase):

    def setUp(self):
        self.manager = VoiceManager()
        self.queue = SpeechQueue()
        self.interrupt = InterruptionEngine(queue_instance=self.queue, manager_instance=self.manager)
        self.wakeword = WakeWordEngine()


    def test_wake_word_detection(self):
        detected, word = self.wakeword.detect_wake_word("Hey HARIKA, open the dashboard.")
        self.assertTrue(detected)
        self.assertEqual(word, "hey harika")

        detected_neg, _ = self.wakeword.detect_wake_word("What is the weather today?")
        self.assertFalse(detected_neg)

    def test_interruption_engine_clears_queue_and_resets_state(self):
        session = self.manager.start_session(continuous=True)
        self.manager.transition_state(VoiceState.THINKING)
        self.manager.transition_state(VoiceState.SPEAKING)

        self.queue.push_text_chunk("Sentence one. Sentence two.")
        self.queue.pop_sentence()

        payload = self.interrupt.handle_interruption(session.session_id)

        self.assertEqual(payload.session_id, session.session_id)
        self.assertEqual(self.manager.get_state(), VoiceState.LISTENING)
        self.assertTrue(self.queue.is_empty())


if __name__ == "__main__":
    unittest.main()
