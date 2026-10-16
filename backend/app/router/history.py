import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.router.schemas import RoutingDecision
from app.core.paths import data_path

logger = logging.getLogger("harika.router.history")


class RouterHistoryManager:
    """Persists detailed routing decision traces to backend/data/router/history.json."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or data_path("router", "history.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.storage_file.exists():
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[RouterHistory] Error loading history file: {e}")
            return []

    def record_decision(self, decision: RoutingDecision) -> RoutingDecision:
        item_dict = decision.model_dump()
        self.history.append(item_dict)
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-300:], f, indent=2, ensure_ascii=False)
            logger.info(f"[RouterHistory] Saved routing decision '{decision.decision_id}' for '{decision.request[:20]}...'.")
        except Exception as e:
            logger.error(f"[RouterHistory] Error saving history file: {e}")
        return decision

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.history[-limit:]))


router_history_manager = RouterHistoryManager()
