import logging
from enum import Enum
from typing import Callable, Dict, List, Any

logger = logging.getLogger("harika.voice.events")


class VoiceEventType(str, Enum):
    VOICE_STARTED = "VoiceStarted"
    VOICE_STOPPED = "VoiceStopped"
    LISTENING_STARTED = "ListeningStarted"
    SPEAKING_STARTED = "SpeakingStarted"
    SPEAKING_STOPPED = "SpeakingStopped"
    INTERRUPTED = "Interrupted"
    CONVERSATION_ENDED = "ConversationEnded"


class VoiceEventBus:
    """Observer Pattern Event Bus emitting events when voice session states change."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[str, Any], None]]] = {
            event_type.value: [] for event_type in VoiceEventType
        }

    def subscribe(self, event_type: VoiceEventType, callback: Callable[[str, Any], None]) -> None:
        if event_type.value in self._subscribers:
            self._subscribers[event_type.value].append(callback)

    def emit(self, event_type: VoiceEventType, payload: Any) -> None:
        event_name = event_type.value
        subscribers = self._subscribers.get(event_name, [])
        logger.info(f"[VoiceEvent] {event_name} emitted.")

        for callback in subscribers:
            try:
                callback(event_name, payload)
            except Exception as e:
                logger.error(f"Error executing voice subscriber for {event_name}: {e}")


voice_event_bus = VoiceEventBus()
