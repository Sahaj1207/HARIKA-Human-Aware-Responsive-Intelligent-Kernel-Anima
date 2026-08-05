import logging
from typing import Dict, Any, Optional, List
from app.agents.schemas import AgentStatus, AgentState
from app.agents.manager import agent_manager, AgentManager

logger = logging.getLogger("harika.agents.scheduler")


class AgentScheduler:
    """Handles immediate, delayed, and queued agent task execution scheduling."""

    def __init__(self, manager: Optional[AgentManager] = None):
        self.manager = manager or agent_manager
        self._queue: List[str] = []

    def schedule_immediate(self, agent_id: str) -> AgentStatus:
        logger.info(f"[AgentScheduler] Immediate execution scheduled for Agent '{agent_id}'.")
        return self.manager.start_agent(agent_id)

    def queue_agent(self, agent_id: str) -> None:
        if agent_id not in self._queue:
            self._queue.append(agent_id)
            logger.info(f"[AgentScheduler] Queued Agent '{agent_id}'. Queue length: {len(self._queue)}.")

    def get_queue(self) -> List[str]:
        return list(self._queue)


agent_scheduler = AgentScheduler()
