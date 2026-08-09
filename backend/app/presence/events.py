import logging
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger("harika.presence.events")


class PresenceEventType(str, Enum):
    PRESENCE_STATE_UPDATED = "PresenceStateUpdated"
    ATTENTION_CHANGED = "AttentionChanged"
    GOAL_INFERRED = "GoalInferred"
    CONTRADICTION_RESOLVED = "ContradictionResolved"
    REFLECTION_COMPLETED = "ReflectionCompleted"
    VERIFICATION_COMPLETED = "VerificationCompleted"
    INITIATIVE_SUGGESTED = "InitiativeSuggested"


class PresenceEventBus:
    """Observer pattern event bus for Presence Engine events."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            et.value: [] for et in PresenceEventType
        }

    def subscribe(self, event_type: PresenceEventType, callback: Callable[[str, Any], None]) -> None:
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)

    def emit(self, event_type: PresenceEventType, payload: Any) -> None:
        name = event_type.value
        logger.info(f"[PresenceEvent] {name} emitted.")
        for cb in self._subscribers.get(name, []):
            try:
                cb(name, payload)
            except Exception as e:
                logger.error(f"Error in presence subscriber for {name}: {e}")


presence_event_bus = PresenceEventBus()
