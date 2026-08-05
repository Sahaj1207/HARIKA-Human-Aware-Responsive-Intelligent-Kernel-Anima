import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.planning.schemas import Goal, GoalStatus, GoalPriority
from app.planning.events import planning_event_bus, PlanningEventType

logger = logging.getLogger("harika.planning.goals")


class GoalManager:
    """Manages active, completed, cancelled, and failed goals with JSON resumption persistence."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or (Path(__file__).resolve().parent.parent.parent / "data" / "planning" / "goals.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.goals: Dict[str, Goal] = self._restore_goals()

    def _restore_goals(self) -> Dict[str, Goal]:
        if not self.storage_file.exists():
            return {}
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                restored = {g["id"]: Goal(**g) for g in data}
                logger.info(f"[GoalManager] Restored {len(restored)} goals from persistent storage.")
                return restored
        except Exception as e:
            logger.error(f"[GoalManager] Error restoring goals: {e}")
            return {}

    def _save_goals(self) -> None:
        try:
            serialized = [g.model_dump() for g in self.goals.values()]
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[GoalManager] Error saving goals: {e}")

    def create_goal(
        self,
        title: str,
        description: str = "",
        priority: GoalPriority = GoalPriority.NORMAL
    ) -> Goal:
        goal_id = f"goal-{uuid.uuid4().hex[:8]}"
        goal = Goal(
            id=goal_id,
            title=title,
            description=description,
            priority=priority,
            status=GoalStatus.ACTIVE,
            progress=0.0,
        )
        self.goals[goal_id] = goal
        self._save_goals()
        planning_event_bus.emit(PlanningEventType.GOAL_CREATED, goal.model_dump())
        logger.info(f"[GoalManager] Created Goal: '{title}' ({priority.value})")
        return goal

    def get_active_goals(self) -> List[Goal]:
        """Returns active goals ordered by priority (CRITICAL > HIGH > NORMAL > LOW > BACKGROUND) then created_at."""
        priority_map = {
            GoalPriority.CRITICAL: 50,
            GoalPriority.HIGH: 40,
            GoalPriority.NORMAL: 30,
            GoalPriority.LOW: 20,
            GoalPriority.BACKGROUND: 10,
        }
        active = [g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]
        # Sort by priority weight descending (-priority), then created_at ascending
        active.sort(key=lambda g: (-priority_map.get(g.priority, 30), g.created_at))
        return active

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self.goals.get(goal_id)

    def cancel_goal(self, goal_id: str) -> bool:
        if goal_id in self.goals:
            g = self.goals[goal_id]
            if g.status == GoalStatus.CANCELLED:
                return True
            g.status = GoalStatus.CANCELLED
            g.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_goals()
            planning_event_bus.emit(PlanningEventType.GOAL_CANCELLED, {"id": goal_id, "title": g.title})
            logger.info(f"[GoalManager] Cancelled Goal: '{g.title}'")
            return True
        return False

    def complete_goal(self, goal_id: str) -> bool:
        if goal_id in self.goals:
            g = self.goals[goal_id]
            g.status = GoalStatus.COMPLETED
            g.progress = 100.0
            g.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_goals()
            logger.info(f"[GoalManager] Completed Goal: '{g.title}'")
            return True
        return False


goal_manager = GoalManager()

