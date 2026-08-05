import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.vision.schemas import VisionHistoryItem, VisionResult

logger = logging.getLogger("harika.vision.history")


class VisionHistoryManager:
    """Manages persistent vision processing history stored in backend/data/vision/history.json."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or (Path(__file__).resolve().parent.parent.parent / "data" / "vision" / "history.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.storage_file.exists():
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[VisionHistory] Error loading history: {e}")
            return []

    def record_result(self, result: VisionResult) -> VisionHistoryItem:
        item = VisionHistoryItem(
            id=result.id,
            filename=result.filename,
            file_type=result.file_type,
            provider=result.provider,
            model=result.model,
            latency_ms=result.latency_ms,
            result_summary=result.summary,
            timestamp=result.timestamp
        )
        self.history.append(item.model_dump())
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-200:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[VisionHistory] Error saving history: {e}")
        return item

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.history[-limit:]))


vision_history_manager = VisionHistoryManager()
