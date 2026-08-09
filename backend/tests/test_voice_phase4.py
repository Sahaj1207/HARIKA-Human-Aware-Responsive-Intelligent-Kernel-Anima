import shutil
import tempfile
import unittest
from pathlib import Path
from app.voice.schemas import VoiceSession, VoiceState, LatencyMetrics
from app.voice.history import VoiceHistoryManager
from app.voice.metrics import VoiceMetricsManager
from app.voice.events import voice_event_bus, VoiceEventType


class TestVoicePhase4(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_file = Path(self.test_dir) / "voice_history.json"
        self.history = VoiceHistoryManager(storage_file=self.storage_file)
        self.metrics = VoiceMetricsManager(history=self.history)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_history_recording_and_persistence(self):
        session = VoiceSession(session_id="vses-100", state=VoiceState.IDLE, turn_count=3, interruption_count=1)
        item = self.history.record_session(session, duration_s=12.5, commands_count=1)

        self.assertEqual(item.session_id, "vses-100")
        self.assertEqual(item.turns_count, 3)

        reloaded = VoiceHistoryManager(storage_file=self.storage_file)
        records = reloaded.get_history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["session_id"], "vses-100")

    def test_metrics_latency_breakdown(self):
        self.metrics.record_latency(
            LatencyMetrics(
                recognition_latency_ms=120.0,
                llm_latency_ms=300.0,
                tts_generation_latency_ms=50.0,
                speech_duration_ms=2000.0,
                end_to_end_latency_ms=470.0
            )
        )
        m = self.metrics.get_metrics()
        self.assertEqual(m.average_recognition_latency_ms, 120.0)
        self.assertEqual(m.average_speech_latency_ms, 50.0)
        self.assertEqual(m.average_e2e_latency_ms, 470.0)

    def test_event_bus_emissions(self):
        events = []
        for et in VoiceEventType:
            voice_event_bus.subscribe(et, lambda name, p: events.append(name))

        voice_event_bus.emit(VoiceEventType.VOICE_STARTED, {})
        voice_event_bus.emit(VoiceEventType.LISTENING_STARTED, {})
        voice_event_bus.emit(VoiceEventType.SPEAKING_STARTED, {})
        voice_event_bus.emit(VoiceEventType.INTERRUPTED, {})
        voice_event_bus.emit(VoiceEventType.CONVERSATION_ENDED, {})

        self.assertEqual(len(events), 5)


if __name__ == "__main__":
    unittest.main()
