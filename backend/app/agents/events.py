import logging
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger("harika.agents.events")


class AgentEventType(str, Enum):
    AGENT_CREATED = "AgentCreated"
    AGENT_STARTED = "AgentStarted"
    TASK_STARTED = "TaskStarted"
    TASK_COMPLETED = "TaskCompleted"
    TASK_FAILED = "TaskFailed"
    AGENT_PAUSED = "AgentPaused"
    AGENT_RESUMED = "AgentResumed"
    AGENT_CANCELLED = "AgentCancelled"
    AGENT_COMPLETED = "AgentCompleted"


class AgentEventBus:
    """Observer Pattern Event Bus emitting events when agent states or tasks change."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            event_type.value: [] for event_type in AgentEventType
        }

    def subscribe(self, event_type: AgentEventType, callback: Callable[[str, Any], None]) -> None:
        """Register a subscriber callback for a specific agent event."""
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)

    def emit(self, event_type: AgentEventType, payload: Any) -> None:
        """Publish an agent event to all registered subscribers."""
        event_name = event_type.value
        subscribers = self._subscribers.get(event_name, [])
        logger.info(f"[AgentEvent] {event_name} emitted.")

        for callback in subscribers:
            try:
                callback(event_name, payload)
            except Exception as e:
                logger.error(f"Error executing agent subscriber for {event_name}: {e}")


agent_event_bus = AgentEventBus()
