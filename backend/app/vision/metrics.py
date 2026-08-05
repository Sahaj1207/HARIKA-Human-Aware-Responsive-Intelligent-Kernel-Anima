import logging
from typing import Dict, Any, Optional
from app.vision.schemas import VisionMetrics
from app.vision.history import vision_history_manager, VisionHistoryManager

logger = logging.getLogger("harika.vision.metrics")


class VisionMetricsManager:
    """Calculates vision metrics, OCR latency, provider usage, and processing statistics."""

    def __init__(self, history: Optional[VisionHistoryManager] = None):
        self.history = history or vision_history_manager

    def get_metrics(self) -> VisionMetrics:
        records = self.history.get_history(limit=500)
        total = len(records)

        if total == 0:
            return VisionMetrics(
                images_analyzed=0,
                pdfs_processed=0,
                total_ocr_requests=0,
                average_ocr_latency_ms=0.0,
                average_analysis_time_ms=0.0,
                failure_rate_percent=0.0,
                provider_usage={}
            )

        images_count = sum(1 for r in records if "pdf" not in r.get("file_type", "").lower())
        pdfs_count = sum(1 for r in records if "pdf" in r.get("file_type", "").lower())

        provider_usage: Dict[str, int] = {}
        total_latency = 0.0

        for r in records:
            p = r.get("provider", "local")
            provider_usage[p] = provider_usage.get(p, 0) + 1
            total_latency += r.get("latency_ms", 10.0)

        avg_lat = round(total_latency / total, 2)

        return VisionMetrics(
            images_analyzed=images_count,
            pdfs_processed=pdfs_count,
            total_ocr_requests=total,
            average_ocr_latency_ms=avg_lat,
            average_analysis_time_ms=avg_lat,
            failure_rate_percent=0.0,
            provider_usage=provider_usage
        )


vision_metrics_manager = VisionMetricsManager()
