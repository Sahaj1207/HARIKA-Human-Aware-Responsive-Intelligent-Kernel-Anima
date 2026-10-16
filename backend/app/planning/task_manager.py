import json
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Optional
from app.planning.schemas import Task, GoalPriority
from app.planning.events import planning_event_bus, PlanningEventType
from app.core.paths import data_path

logger = logging.getLogger("harika.planning.tasks")


class TaskManager:
    """Manages subtask decompositions, persistence, cancellation, and task dependency execution locks."""

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or data_path("planning", "tasks.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, Task] = self._restore_tasks()

    def _restore_tasks(self) -> Dict[str, Task]:
        if not self.storage_file.exists():
            return {}
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                restored = {t["id"]: Task(**t) for t in data}
                logger.info(f"[TaskManager] Restored {len(restored)} tasks from persistent storage.")
                return restored
        except Exception as e:
            logger.error(f"[TaskManager] Error restoring tasks: {e}")
            return {}

    def _save_tasks(self) -> None:
        try:
            serialized = [t.model_dump() for t in self.tasks.values()]
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[TaskManager] Error saving tasks: {e}")

    def create_task(
        self,
        goal_id: str,
        title: str,
        priority: GoalPriority = GoalPriority.NORMAL,
        depends_on: Optional[List[str]] = None,
        tool_required: Optional[str] = None
    ) -> Task:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = Task(
            id=task_id,
            goal_id=goal_id,
            title=title,
            priority=priority,
            depends_on=depends_on or [],
            tool_required=tool_required,
            completed=False,
            status="pending"
        )
        self.tasks[task_id] = task
        self._save_tasks()
        planning_event_bus.emit(PlanningEventType.TASK_CREATED, task.model_dump())
        logger.info(f"[TaskManager] Created Task: '{title}' for Goal {goal_id}")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def can_execute_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task or task.completed or task.status in ["completed", "cancelled", "failed"]:
            return False

        # Enforce task dependency checks
        for dep_id in task.depends_on:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or not dep_task.completed:
                logger.warning(f"[TaskManager] Execution REFUSED for task '{task.title}': Dependent task '{dep_id}' incomplete.")
                return False
        return True

    def complete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            t = self.tasks[task_id]
            if not self.can_execute_task(task_id) and t.depends_on:
                logger.error(f"[TaskManager] Cannot complete task '{t.title}' - dependencies not met.")
                return False
            t.completed = True
            t.status = "completed"
            self._save_tasks()
            planning_event_bus.emit(PlanningEventType.TASK_COMPLETED, {"id": task_id, "title": t.title})
            logger.info(f"[TaskManager] Completed Task: '{t.title}'")
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = "cancelled"
            t.completed = False
            self._save_tasks()
            logger.info(f"[TaskManager] Cancelled Task: '{t.title}'")
            return True
        return False

    def get_tasks_for_goal(self, goal_id: str) -> List[Task]:
        return [t for t in self.tasks.values() if t.goal_id == goal_id]


task_manager = TaskManager()

