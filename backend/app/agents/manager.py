import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from app.agents.schemas import AgentStatus, AgentState, AgentContext
from app.agents.state_machine import agent_state_machine, AgentStateMachine, InvalidAgentStateTransitionError
from app.agents.events import agent_event_bus, AgentEventType

logger = logging.getLogger("harika.agents.manager")


class AgentManager:
    """Single Facade Entry Point orchestrating agent creation, resumption, pausing, cancellation, and status tracking."""

    def __init__(self):
        self._agents: Dict[str, AgentStatus] = {}
        self._contexts: Dict[str, AgentContext] = {}

    def create_agent(
        self,
        goal_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        user_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentStatus:
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        status = AgentStatus(
            agent_id=agent_id,
            goal_id=goal_id,
            plan_id=plan_id,
            state=AgentState.CREATED,
            progress_percent=0.0,
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        context = AgentContext(
            user_id=user_id,
            goal_id=goal_id,
            plan_id=plan_id,
            metadata=metadata or {}
        )

        self._agents[agent_id] = status
        self._contexts[agent_id] = context

        # State transition: CREATED -> READY
        agent_state_machine.transition(status, AgentState.READY)

        agent_event_bus.emit(AgentEventType.AGENT_CREATED, status.model_dump())
        logger.info(f"[AgentManager] Created Agent '{agent_id}' for Goal '{goal_id}'.")
        return status

    def get_agent_status(self, agent_id: str) -> Optional[AgentStatus]:
        return self._agents.get(agent_id)

    def list_active_agents(self) -> List[AgentStatus]:
        return list(self._agents.values())

    def start_agent(self, agent_id: str) -> AgentStatus:
        status = self.get_agent_status(agent_id)
        if not status:
            raise ValueError(f"Agent '{agent_id}' not found.")
        agent_state_machine.transition(status, AgentState.RUNNING)
        agent_event_bus.emit(AgentEventType.AGENT_STARTED, status.model_dump())
        logger.info(f"[AgentManager] Started Agent '{agent_id}'.")
        return status

    def pause_agent(self, agent_id: str) -> AgentStatus:
        status = self.get_agent_status(agent_id)
        if not status:
            raise ValueError(f"Agent '{agent_id}' not found.")
        agent_state_machine.transition(status, AgentState.PAUSED)
        agent_event_bus.emit(AgentEventType.AGENT_PAUSED, status.model_dump())
        logger.info(f"[AgentManager] Paused Agent '{agent_id}'.")
        return status

    def resume_agent(self, agent_id: str) -> AgentStatus:
        status = self.get_agent_status(agent_id)
        if not status:
            raise ValueError(f"Agent '{agent_id}' not found.")
        agent_state_machine.transition(status, AgentState.RUNNING)
        agent_event_bus.emit(AgentEventType.AGENT_RESUMED, status.model_dump())
        logger.info(f"[AgentManager] Resumed Agent '{agent_id}'.")
        return status

    def cancel_agent(self, agent_id: str) -> AgentStatus:
        status = self.get_agent_status(agent_id)
        if not status:
            raise ValueError(f"Agent '{agent_id}' not found.")
        agent_state_machine.transition(status, AgentState.CANCELLED)
        agent_event_bus.emit(AgentEventType.AGENT_CANCELLED, status.model_dump())
        logger.info(f"[AgentManager] Cancelled Agent '{agent_id}'.")
        return status

    async def execute_agent_goal(
        self,
        user_message: str,
        goal_id: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Full end-to-end agent goal execution orchestrating Planning, Tools, Vision, Memory, and Reflection."""
        from app.planning.manager import planning_manager
        from app.agents.orchestrator import agent_orchestrator
        from app.agents.history import agent_history_manager
        from app.memory.manager import memory_manager
        from app.memory.models import MemoryItem, MemoryCategory

        # 1. Create or resolve Goal & Plan
        if not goal_id:
            goal = planning_manager.create_goal(title=f"Goal for '{user_message[:30]}'", description=user_message)
            goal_id = goal.id

        from app.tools.manager import tool_manager
        action_plan = tool_manager.plan_action(user_message)
        tool_action = action_plan.actions[0].model_dump() if action_plan.is_tool_action and action_plan.actions else None

        plan = planning_manager.create_plan(user_message=user_message, goal_id=goal_id, tool_action=tool_action)


        # 2. Create and Start Agent
        status = self.create_agent(goal_id=goal_id, plan_id=plan.id, user_id=user_id)
        self.start_agent(status.agent_id)

        # 3. Execute plan step via AgentOrchestrator
        t_res = await agent_orchestrator.execute_plan_step(status, plan, file_bytes=file_bytes, filename=filename)

        if t_res.success:
            agent_state_machine.transition(status, AgentState.COMPLETED)
            agent_event_bus.emit(AgentEventType.AGENT_COMPLETED, status.model_dump())

            # 4. Memory Integration: Store structured fact summary
            try:
                mem_item = MemoryItem(
                    id=f"mem-agt-{uuid.uuid4().hex[:8]}",
                    category=MemoryCategory.TASKS,
                    title=f"Completed Agent Goal: {user_message[:40]}",
                    content=f"Agent '{status.agent_id}' completed task '{t_res.title}' in {t_res.duration_ms}ms. Output: {str(t_res.output)[:200]}",
                    importance=0.8,
                    confidence=0.95,
                    source="agent_engine",
                    tags=["agent", "task_completed"]
                )
                memory_manager.add_memory(mem_item, user_id=user_id)
            except Exception as e:
                logger.error(f"[AgentManager] Failed memory integration: {e}")
        else:
            agent_state_machine.transition(status, AgentState.FAILED)
            agent_event_bus.emit(AgentEventType.TASK_FAILED, status.model_dump())

        # 5. Record History
        agent_history_manager.record_agent_execution(
            agent_status=status,
            result_summary=f"Task '{t_res.title}' {'completed successfully' if t_res.success else 'failed'}",
            duration_ms=t_res.duration_ms
        )

        return {
            "agent_id": status.agent_id,
            "goal_id": goal_id,
            "plan_id": plan.id,
            "status": status.state.value,
            "task_result": t_res.model_dump()
        }


agent_manager = AgentManager()

