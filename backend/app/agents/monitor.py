import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.agents.schemas import AgentStatus, AgentState
from app.agents.manager import agent_manager, AgentManager

logger = logging.getLogger("harika.agents.monitor")


class AgentMonitor:
    """Live Agent Monitoring Engine tracking progress, task execution, retries, and duration."""

    def __init__(self, manager: Optional[AgentManager] = None):
        self.manager = manager or agent_manager
        self._start_times: Dict[str, float] = {}

    def record_start(self, agent_id: str) -> None:
        self._start_times[agent_id] = time.time()

    def get_live_status(self, agent_id: str) -> Optional[AgentStatus]:
        status = self.manager.get_agent_status(agent_id)
        if not status:
            return None

        if agent_id in self._start_times:
            status.running_duration_s = round(time.time() - self._start_times[agent_id], 2)

        return status


agent_monitor = AgentMonitor()
