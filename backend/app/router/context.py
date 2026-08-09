import logging
from typing import Dict, Any, List, Optional
from app.router.schemas import RequestContext

logger = logging.getLogger("harika.router.context")


class ContextBuilder:
    """Builds a comprehensive RequestContext object before intent classification."""

    def build_context(
        self,
        message: str,
        user_id: str = "default",
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> RequestContext:
        history = conversation_history or []

        # Gather active states from subsystems
        active_agent_id = None
        try:
            from app.agents.manager import agent_manager
            active_agents = agent_manager.list_active_agents()
            if active_agents:
                ag = active_agents[0]
                active_agent_id = getattr(ag, "agent_id", None) or (ag.get("agent_id") if isinstance(ag, dict) else None)

        except Exception:
            pass

        active_goal_id = None
        try:
            from app.planning.goals import goal_manager
            goals = goal_manager.get_active_goals()
            if goals:
                active_goal_id = goals[0].id
        except Exception:
            pass

        voice_st = "idle"
        try:
            from app.voice.manager import voice_manager
            voice_st = voice_manager.get_state().value
        except Exception:
            pass

        recent_mems: List[str] = []
        try:
            from app.memory.manager import memory_manager
            mems = memory_manager.get_memories(user_id=user_id, limit=3)
            recent_mems = [m.title for m in mems]
        except Exception:
            pass

        ctx = RequestContext(
            message=message,
            user_id=user_id,
            session_id=session_id,
            conversation_history=history[-5:],
            active_goal_id=active_goal_id,
            active_agent_id=active_agent_id,
            recent_memories=recent_mems,
            voice_state=voice_st
        )

        logger.info(f"[ContextBuilder] Built RequestContext for message '{message[:30]}...' (agent={active_agent_id}, goal={active_goal_id}).")
        return ctx


context_builder = ContextBuilder()
