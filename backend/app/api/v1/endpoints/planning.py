from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.planning.manager import planning_manager
from app.planning.schemas import (
    Goal, Task, Plan, PlanStep, Reflection, PlanningMetrics, GoalPriority
)

router = APIRouter()


class CreateGoalPayload(BaseModel):
    title: str = Field(..., example="Build React App")
    description: str = Field(default="", example="Create and run Vite React application")
    priority: GoalPriority = Field(default=GoalPriority.NORMAL)


class CreateTaskPayload(BaseModel):
    goal_id: str = Field(..., example="goal-12345678")
    title: str = Field(..., example="Setup Database Schema")
    priority: GoalPriority = Field(default=GoalPriority.NORMAL)
    depends_on: List[str] = Field(default_factory=list, example=["task-11111111"])
    tool_required: Optional[str] = None


class CreatePlanPayload(BaseModel):
    user_message: str = Field(..., example="Create a React project")
    goal_id: Optional[str] = None
    custom_steps: Optional[List[PlanStep]] = None


class ExecuteStepPayload(BaseModel):
    plan: Plan


class CreateReflectionPayload(BaseModel):
    user_message: str
    assistant_response: str
    was_tool_used: bool = False
    tool_name: Optional[str] = None
    success: bool = True
    lessons_learned: Optional[str] = None
    next_recommendation: Optional[str] = None


@router.get("", response_model=List[Goal])
async def list_active_goals():
    """Returns active goals ordered by priority (CRITICAL > HIGH > NORMAL > LOW > BACKGROUND)."""
    return planning_manager.get_active_goals()


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_planning_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns plan execution history log."""
    return planning_manager.get_history(limit=limit)


@router.get("/metrics", response_model=PlanningMetrics)
async def get_planning_metrics():
    """Returns Reflection & Planning Engine analytics and metrics."""
    return planning_manager.get_metrics()


@router.post("/goals", response_model=Goal)
async def create_goal(payload: CreateGoalPayload):
    """Creates a new goal with priority."""
    return planning_manager.create_goal(payload.title, payload.description, payload.priority)


@router.delete("/goals/{goal_id}")
async def cancel_goal(goal_id: str):
    """Cancels an active goal."""
    success = planning_manager.cancel_goal(goal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"status": "success", "message": f"Cancelled goal {goal_id}"}


@router.post("/tasks", response_model=Task)
async def create_task(payload: CreateTaskPayload):
    """Creates a new task supporting dependency locks via depends_on."""
    return planning_manager.create_task(
        goal_id=payload.goal_id,
        title=payload.title,
        priority=payload.priority,
        depends_on=payload.depends_on,
        tool_required=payload.tool_required
    )


@router.get("/goals/{goal_id}/tasks", response_model=List[Task])
async def get_tasks_for_goal(goal_id: str):
    """Gets all tasks associated with a goal."""
    return planning_manager.get_tasks_for_goal(goal_id)


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str):
    """Completes a task, enforcing dependency execution locks."""
    if not planning_manager.can_execute_task(task_id):
        task = planning_manager.tasks.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
        raise HTTPException(status_code=400, detail="Cannot complete task: prerequisite tasks in depends_on are incomplete.")
    
    success = planning_manager.complete_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to complete task.")
    return {"status": "success", "message": f"Completed task {task_id}"}


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancels a task."""
    success = planning_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"status": "success", "message": f"Cancelled task {task_id}"}


@router.post("/plan", response_model=Plan)
async def generate_plan(payload: CreatePlanPayload):
    """Generates a structured plan moving CREATED -> VALIDATED -> READY state."""
    return planning_manager.create_plan(payload.user_message, payload.goal_id, custom_steps=payload.custom_steps)


@router.post("/plan/execute-step")
async def execute_plan_step_0(payload: ExecuteStepPayload):
    """Sprint 10 single-step execution: Executes ONLY steps[0]."""
    try:
        return planning_manager.execute_step_0(payload.plan)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reflect", response_model=Reflection)
async def record_reflection(payload: CreateReflectionPayload):
    """Records a clean post-response interaction reflection without storing chain-of-thought."""
    return planning_manager.record_reflection(
        user_message=payload.user_message,
        assistant_response=payload.assistant_response,
        was_tool_used=payload.was_tool_used,
        tool_name=payload.tool_name,
        success=payload.success
    )

