import logging
from typing import Dict, List, Any, Optional
from app.planning.schemas import (
    Goal, Task, Plan, PlanStep, Decision, Reflection, PlanningMetrics, GoalPriority
)
from app.planning.goal_manager import goal_manager, GoalManager
from app.planning.task_manager import task_manager, TaskManager
from app.planning.decision_engine import decision_engine, DecisionEngine
from app.planning.planner import hierarchical_planner, HierarchicalPlanner
from app.planning.reflection import reflection_engine, ReflectionEngine
from app.planning.history import plan_history, PlanHistory
from app.planning.metrics import planning_metrics_manager, PlanningMetricsManager

logger = logging.getLogger("harika.planning.manager")


class PlanningManager:
    """Central Facade Entry Point orchestrating Goals, Tasks, Decisions, Plans, Reflections, and Metrics."""

    def __init__(
        self,
        goals: Optional[GoalManager] = None,
        tasks: Optional[TaskManager] = None,
        decisions: Optional[DecisionEngine] = None,
        planner: Optional[HierarchicalPlanner] = None,
        reflections: Optional[ReflectionEngine] = None,
        history: Optional[PlanHistory] = None,
        metrics: Optional[PlanningMetricsManager] = None,
    ):
        self.goals = goals or goal_manager
        self.tasks = tasks or task_manager
        self.decisions = decisions or decision_engine
        self.planner = planner or hierarchical_planner
        self.reflections = reflections or reflection_engine
        self.history = history or plan_history
        self.metrics = metrics or planning_metrics_manager

    # --- Goal Operations ---
    def get_active_goals(self) -> List[Goal]:
        return self.goals.get_active_goals()

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        return self.goals.get_goal(goal_id)

    def create_goal(self, title: str, description: str = "", priority: GoalPriority = GoalPriority.NORMAL) -> Goal:
        return self.goals.create_goal(title, description, priority)

    def cancel_goal(self, goal_id: str) -> bool:
        return self.goals.cancel_goal(goal_id)

    def complete_goal(self, goal_id: str) -> bool:
        return self.goals.complete_goal(goal_id)

    # --- Task Operations ---
    def create_task(
        self,
        goal_id: str,
        title: str,
        priority: GoalPriority = GoalPriority.NORMAL,
        depends_on: Optional[List[str]] = None,
        tool_required: Optional[str] = None
    ) -> Task:
        return self.tasks.create_task(goal_id, title, priority, depends_on, tool_required)

    def can_execute_task(self, task_id: str) -> bool:
        return self.tasks.can_execute_task(task_id)

    def complete_task(self, task_id: str) -> bool:
        return self.tasks.complete_task(task_id)

    def cancel_task(self, task_id: str) -> bool:
        return self.tasks.cancel_task(task_id)

    def get_tasks_for_goal(self, goal_id: str) -> List[Task]:
        return self.tasks.get_tasks_for_goal(goal_id)

    # --- Decision Operations ---
    def evaluate_decision(self, user_message: str, is_tool_action: bool = False, tool_name: Optional[str] = None) -> Decision:
        return self.decisions.evaluate_decision(user_message, is_tool_action, tool_name)

    # --- Plan Operations ---
    def create_plan(
        self,
        user_message: str,
        goal_id: Optional[str] = None,
        tool_action: Optional[Dict[str, Any]] = None,
        custom_steps: Optional[List[PlanStep]] = None
    ) -> Plan:
        return self.planner.create_plan(user_message, goal_id, tool_action, custom_steps)

    def execute_step_0(self, plan: Plan) -> Dict[str, Any]:
        """Sprint 10 single-step execution: Executes ONLY steps[0]."""
        res = self.planner.execute_step_0(plan)
        # Record plan execution in history
        self.history.record_plan_execution({
            "plan_id": plan.id,
            "state": plan.state.value,
            "steps_count": len(plan.steps),
            "executed_step": res["executed_step"]
        })
        return res

    def replan(self, plan: Plan, new_steps: List[PlanStep]) -> Plan:
        return self.planner.replan(plan, new_steps)

    def cancel_plan(self, plan: Plan) -> Plan:
        return self.planner.cancel_plan(plan)

    # --- Reflection & Analytics Operations ---
    def record_reflection(
        self,
        user_message: str,
        assistant_response: str,
        was_tool_used: bool = False,
        tool_name: Optional[str] = None,
        success: bool = True
    ) -> Reflection:
        return self.reflections.reflect_on_interaction(
            user_message=user_message,
            assistant_response=assistant_response,
            was_tool_used=was_tool_used,
            tool_name=tool_name,
            success=success
        )

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.history.get_history(limit=limit)

    def get_metrics(self) -> PlanningMetrics:
        return self.metrics.get_metrics()


planning_manager = PlanningManager()

