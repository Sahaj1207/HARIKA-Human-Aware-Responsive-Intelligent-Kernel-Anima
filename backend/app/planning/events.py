import logging
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger("harika.planning.events")


class PlanningEventType(str, Enum):
    GOAL_CREATED = "GoalCreated"
    GOAL_CANCELLED = "GoalCancelled"
    TASK_CREATED = "TaskCreated"
    TASK_COMPLETED = "TaskCompleted"
    DECISION_MADE = "DecisionMade"
    REFLECTION_STORED = "ReflectionStored"
    VISION_STARTED = "VisionStarted"
    VISION_COMPLETED = "VisionCompleted"
    OCR_COMPLETED = "OCRCompleted"
    PDF_PROCESSED = "PDFProcessed"
    VISION_FAILED = "VisionFailed"



class PlanningEventBus:
    """Observer Pattern Event Bus emitting events when planning states change."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            event_type.value: [] for event_type in PlanningEventType
        }

    def subscribe(self, event_type: PlanningEventType, callback: Callable[[str, Any], None]) -> None:
        """Register a subscriber callback for a specific planning event."""
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)

    def emit(self, event_type: PlanningEventType, payload: Any) -> None:
        """Publish a planning event to all registered subscribers."""
        event_name = event_type.value
        subscribers = self._subscribers.get(event_name, [])
        logger.info(f"[PlanningEvent] {event_name} emitted.")
        
        for callback in subscribers:
            try:
                callback(event_name, payload)
            except Exception as e:
                logger.error(f"Error executing planning observer subscriber for {event_name}: {e}")


planning_event_bus = PlanningEventBus()
