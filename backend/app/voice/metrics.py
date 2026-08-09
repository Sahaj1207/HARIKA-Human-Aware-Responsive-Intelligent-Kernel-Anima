import logging
from typing import Dict, Any, Optional
from app.voice.schemas import VoiceMetrics, LatencyMetrics
from app.voice.history import voice_history_manager, VoiceHistoryManager

logger = logging.getLogger("harika.voice.metrics")


class VoiceMetricsManager:
    """Tracks latency metrics (recognition, LLM, TTS generation, E2E), total sessions, and interruptions."""

    def __init__(self, history: Optional[VoiceHistoryManager] = None):
        self.history = history or voice_history_manager
        self._latest_latency = LatencyMetrics()

    def record_latency(self, latency: LatencyMetrics) -> None:
        self._latest_latency = latency

    def get_metrics(self) -> VoiceMetrics:
        records = self.history.get_history(limit=500)
        total = len(records)

        if total == 0:
            return VoiceMetrics(
                total_sessions=0,
                average_duration_s=0.0,
                total_interruptions=0,
                average_recognition_latency_ms=self._latest_latency.recognition_latency_ms,
                average_speech_latency_ms=self._latest_latency.tts_generation_latency_ms,
                average_e2e_latency_ms=self._latest_latency.end_to_end_latency_ms
            )

        total_duration = sum(r.get("duration_s", 0.0) for r in records)
        total_interruptions = sum(r.get("interruptions_count", 0) for r in records)

        return VoiceMetrics(
            total_sessions=total,
            average_duration_s=round(total_duration / total, 2),
            total_interruptions=total_interruptions,
            average_recognition_latency_ms=self._latest_latency.recognition_latency_ms,
            average_speech_latency_ms=self._latest_latency.tts_generation_latency_ms,
            average_e2e_latency_ms=self._latest_latency.end_to_end_latency_ms
        )


voice_metrics_manager = VoiceMetricsManager()
