import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from app.voice.schemas import VoiceState, VoiceSession, LatencyMetrics
from app.voice.manager import VoiceManager
from app.voice.speech_queue import SpeechQueue
from app.voice.speaker import SpeakerCoordinator
from app.voice.interrupt import InterruptionEngine
from app.voice.wakeword import WakeWordEngine
from app.voice.history import VoiceHistoryManager
from app.voice.metrics import VoiceMetricsManager


class TestVoiceAllE2E(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.history_file = Path(self.test_dir) / "voice_history.json"
        self.history = VoiceHistoryManager(storage_file=self.history_file)
        self.metrics = VoiceMetricsManager(history=self.history)
        self.manager = VoiceManager()
        self.queue = SpeechQueue()
        self.speaker = SpeakerCoordinator(queue_instance=self.queue)
        self.interrupt = InterruptionEngine(queue_instance=self.queue, manager_instance=self.manager)
        self.wakeword = WakeWordEngine()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_e2e_wake_word_and_session_flow(self):
        text_stream = "Hey HARIKA, calculate 15 * 6"
        is_wake, word = self.wakeword.detect_wake_word(text_stream)
        self.assertTrue(is_wake)

        session = self.manager.start_session(continuous=True)
        self.assertEqual(session.state, VoiceState.LISTENING)

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            self.manager.process_voice_directive(text_stream)
        )
        loop.close()

        self.assertEqual(res["action_type"], "tool")

        # Trigger interruption
        int_res = self.interrupt.handle_interruption(session.session_id)
        self.assertEqual(int_res.session_id, session.session_id)

        # Stop session
        stopped = self.manager.stop_session()
        self.assertEqual(stopped.state, VoiceState.IDLE)

    def test_e2e_elevenlabs_provider_fallback(self):
        synth = self.manager.synthesize("Hello world", provider_override="elevenlabs")
        self.assertIn("provider", synth)
        self.assertIn(synth["provider"], ["elevenlabs", "elevenlabs_fallback"])

    def test_e2e_metrics_latency_tracking(self):
        self.metrics.record_latency(
            LatencyMetrics(
                recognition_latency_ms=100.0,
                llm_latency_ms=250.0,
                tts_generation_latency_ms=40.0,
                speech_duration_ms=1500.0,
                end_to_end_latency_ms=390.0
            )
        )
        m = self.metrics.get_metrics()
        self.assertEqual(m.average_recognition_latency_ms, 100.0)
        self.assertEqual(m.average_e2e_latency_ms, 390.0)


if __name__ == "__main__":
    unittest.main()
