import uuid
import logging
from typing import Dict, Any, Optional
from app.agents.schemas import AgentTaskResult, AgentStatus, AgentState
from app.agents.executor import task_executor, TaskExecutor
from app.planning.schemas import Plan, PlanStep, PlanState
from app.planning.planner import hierarchical_planner
from app.planning.reflection import reflection_engine
from app.agents.events import agent_event_bus, AgentEventType

logger = logging.getLogger("harika.agents.orchestrator")


class AgentOrchestrator:
    """Orchestrates Planning, Tools, Vision, Memory, and Reflection lifecycle per agent task."""

    def __init__(self, executor: Optional[TaskExecutor] = None):
        self.executor = executor or task_executor

    async def execute_plan_step(
        self,
        agent_status: AgentStatus,
        plan: Plan,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None
    ) -> AgentTaskResult:
        if not plan.steps:
            raise ValueError(f"Plan {plan.id} contains no execution steps.")

        step = plan.steps[0]
        agent_status.current_task = step.title
        agent_event_bus.emit(AgentEventType.TASK_STARTED, {
            "agent_id": agent_status.agent_id,
            "step_number": step.step_number,
            "title": step.title
        })

        # Transition plan: READY -> EXECUTING
        if plan.state == PlanState.READY:
            hierarchical_planner.state_machine.transition(plan, PlanState.EXECUTING)

        # Execute task via TaskExecutor
        task_id = f"tsk-{uuid.uuid4().hex[:8]}"
        res = await self.executor.execute_task(
            task_id=task_id,
            step_number=step.step_number,
            title=step.title,
            tool_name=step.tool_name,
            arguments=step.arguments,
            file_bytes=file_bytes,
            filename=filename
        )

        if res.success:
            agent_status.completed_tasks_count += 1
            agent_status.progress_percent = 100.0
            hierarchical_planner.state_machine.transition(plan, PlanState.COMPLETED)

            # Record reflection
            reflection_engine.reflect_on_interaction(
                user_message=step.title,
                assistant_response=str(res.output),
                was_tool_used=bool(step.tool_name),
                tool_name=step.tool_name,
                success=True
            )

            agent_event_bus.emit(AgentEventType.TASK_COMPLETED, {
                "agent_id": agent_status.agent_id,
                "task_id": task_id,
                "title": step.title,
                "duration_ms": res.duration_ms
            })
        else:
            hierarchical_planner.state_machine.transition(plan, PlanState.FAILED)
            agent_event_bus.emit(AgentEventType.TASK_FAILED, {
                "agent_id": agent_status.agent_id,
                "task_id": task_id,
                "error": res.error
            })

        return res


agent_orchestrator = AgentOrchestrator()
