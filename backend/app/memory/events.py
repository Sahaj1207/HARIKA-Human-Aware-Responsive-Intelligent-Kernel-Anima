import logging
from typing import Callable, Dict, List, Any
from enum import Enum

logger = logging.getLogger("harika.memory.events")


class MemoryEventType(str, Enum):
    MEMORY_CREATED = "MemoryCreated"
    MEMORY_UPDATED = "MemoryUpdated"
    MEMORY_DELETED = "MemoryDeleted"
    MEMORY_MERGED = "MemoryMerged"
    MEMORY_RETRIEVED = "MemoryRetrieved"


class MemoryEventBus:
    """Observer Pattern Event Bus emitting events when memory items change."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            event_type.value: [] for event_type in MemoryEventType
        }

    def subscribe(self, event_type: MemoryEventType, callback: Callable[[str, Any], None]) -> None:
        """Register a subscriber callback for a specific memory event."""
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)
            logger.debug(f"Subscribed callback to memory event: {event_type.value}")

    def emit(self, event_type: MemoryEventType, payload: Any) -> None:
        """Publish a memory event to all registered subscribers."""
        event_name = event_type.value
        subscribers = self._subscribers.get(event_name, [])
        logger.info(f"[MemoryEvent] {event_name} emitted. Payload summary: {payload.get('title', payload.get('id', 'N/A')) if isinstance(payload, dict) else 'Event'}")
        
        for callback in subscribers:
            try:
                callback(event_name, payload)
            except Exception as e:
                logger.error(f"Error executing memory observer subscriber for {event_name}: {e}")


memory_event_bus = MemoryEventBus()
