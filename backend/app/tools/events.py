import logging
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger("harika.tools.events")


class ToolEventType(str, Enum):
    TOOL_STARTED = "ToolStarted"
    TOOL_COMPLETED = "ToolCompleted"
    TOOL_FAILED = "ToolFailed"
    TOOL_CANCELLED = "ToolCancelled"


class ToolEventBus:
    """Observer Pattern Event Bus emitting events when tools execute."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            event_type.value: [] for event_type in ToolEventType
        }

    def subscribe(self, event_type: ToolEventType, callback: Callable[[str, Any], None]) -> None:
        """Register a subscriber callback for a specific tool event."""
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)
            logger.debug(f"Subscribed callback to tool event: {event_type.value}")

    def emit(self, event_type: ToolEventType, payload: Any) -> None:
        """Publish a tool event to all registered subscribers."""
        event_name = event_type.value
        subscribers = self._subscribers.get(event_name, [])
        logger.info(f"[ToolEvent] {event_name} emitted for payload: {payload.get('tool_name', 'N/A') if isinstance(payload, dict) else 'Event'}")
        
        for callback in subscribers:
            try:
                callback(event_name, payload)
            except Exception as e:
                logger.error(f"Error executing tool observer subscriber for {event_name}: {e}")


tool_event_bus = ToolEventBus()
