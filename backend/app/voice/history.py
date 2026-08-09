import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.voice.schemas import VoiceHistoryItem, VoiceSession

logger = logging.getLogger("harika.voice.history")


class VoiceHistoryManager:
    """Persists voice session history records in backend/data/voice/history.json."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or (Path(__file__).resolve().parent.parent.parent / "data" / "voice" / "history.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.storage_file.exists():
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[VoiceHistory] Error loading history file: {e}")
            return []

    def record_session(
        self,
        session: VoiceSession,
        duration_s: float = 0.0,
        commands_count: int = 0
    ) -> VoiceHistoryItem:
        item = VoiceHistoryItem(
            session_id=session.session_id,
            duration_s=duration_s,
            turns_count=session.turn_count,
            commands_count=commands_count,
            interruptions_count=session.interruption_count,
            summary=session.summary or f"Voice session with {session.turn_count} turns.",
            timestamp=session.updated_at
        )

        self.history.append(item.model_dump())
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-200:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[VoiceHistory] Error saving history file: {e}")

        return item

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.history[-limit:]))


voice_history_manager = VoiceHistoryManager()
