import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("harika.planning.history")


class PlanHistory:
    """Persists plan execution history records in JSON storage."""

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = history_file or (Path(__file__).resolve().parent.parent.parent / "data" / "planning" / "history.json")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[PlanHistory] Error reading history file: {e}")
            return []

    def record_plan_execution(self, plan_data: Dict[str, Any]) -> None:
        self.history.append(plan_data)
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-100:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[PlanHistory] Error saving history file: {e}")

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.history[-limit:]))


plan_history = PlanHistory()
