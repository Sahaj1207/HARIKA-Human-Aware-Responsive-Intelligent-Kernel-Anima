import logging
from app.presence.schemas import PresenceMetrics

logger = logging.getLogger("harika.presence.metrics")


class PresenceMetricsManager:
    """Tracks telemetry metrics for HARIKA Presence Engine v1.1."""

    def __init__(self):
        self._metrics = PresenceMetrics()

    def record_observation(
        self,
        had_initiative: bool = False,
        reflection_passed: bool = True,
        verification_passed: bool = True,
        had_correction: bool = False,
        latency_ms: float = 0.0
    ) -> None:
        self._metrics.total_observations += 1
        if had_initiative:
            self._metrics.initiatives_offered += 1
        if reflection_passed:
            self._metrics.reflections_passed += 1
        if verification_passed:
            self._metrics.verifications_passed += 1
        if had_correction:
            self._metrics.corrections_repaired += 1

        tot = self._metrics.total_observations
        prev_avg = self._metrics.average_presence_latency_ms
        self._metrics.average_presence_latency_ms = round(((prev_avg * (tot - 1)) + latency_ms) / tot, 2)

    def get_metrics(self) -> PresenceMetrics:
        return self._metrics.model_copy()


presence_metrics_manager = PresenceMetricsManager()
