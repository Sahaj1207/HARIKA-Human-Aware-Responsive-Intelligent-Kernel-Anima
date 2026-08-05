import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.agents.schemas import AgentHistoryItem, AgentStatus

logger = logging.getLogger("harika.agents.history")


class AgentHistoryManager:
    """Persists agent execution history records in backend/data/agents/history.json."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or (Path(__file__).resolve().parent.parent.parent / "data" / "agents" / "history.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.storage_file.exists():
            return []
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[AgentHistory] Error loading history file: {e}")
            return []

    def record_agent_execution(
        self,
        agent_status: AgentStatus,
        result_summary: str,
        duration_ms: float = 0.0
    ) -> AgentHistoryItem:
        item = AgentHistoryItem(
            agent_id=agent_status.agent_id,
            goal_id=agent_status.goal_id,
            plan_id=agent_status.plan_id,
            tasks_count=agent_status.completed_tasks_count,
            duration_ms=duration_ms,
            result_summary=result_summary,
            timestamp=agent_status.updated_at
        )

        self.history.append(item.model_dump())
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-200:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[AgentHistory] Error saving history file: {e}")

        return item

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.history[-limit:]))


agent_history_manager = AgentHistoryManager()
