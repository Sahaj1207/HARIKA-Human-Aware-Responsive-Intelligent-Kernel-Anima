import logging
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger("harika.router.events")


class RouterEventType(str, Enum):
    INTENT_DETECTED = "IntentDetected"
    CONFIDENCE_CALCULATED = "ConfidenceCalculated"
    ENGINE_SELECTED = "EngineSelected"
    ENGINE_STARTED = "EngineStarted"
    ENGINE_COMPLETED = "EngineCompleted"
    FORMATTER_STARTED = "FormatterStarted"
    FORMATTER_COMPLETED = "FormatterCompleted"
    CLARIFICATION_REQUESTED = "ClarificationRequested"
    FALLBACK_ACTIVATED = "FallbackActivated"


class RouterEventBus:
    """Observer Pattern Event Bus emitting router events."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            et.value: [] for et in RouterEventType
        }

    def subscribe(self, event_type: RouterEventType, callback: Callable[[str, Any], None]) -> None:
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)

    def emit(self, event_type: RouterEventType, payload: Any) -> None:
        name = event_type.value
        logger.info(f"[RouterEvent] {name} emitted.")
        for cb in self._subscribers.get(name, []):
            try:
                cb(name, payload)
            except Exception as e:
                logger.error(f"Error in router event subscriber for {name}: {e}")


router_event_bus = RouterEventBus()
