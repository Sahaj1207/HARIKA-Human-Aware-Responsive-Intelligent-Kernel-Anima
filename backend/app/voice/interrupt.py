import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.voice.schemas import VoiceState, VoiceInterruptionPayload
from app.voice.manager import voice_manager
from app.voice.speech_queue import speech_queue, SpeechQueue

logger = logging.getLogger("harika.voice.interrupt")


class InterruptionEngine:
    """Handles immediate speech cancellation, SpeechQueue clearing, and state transition to LISTENING upon user interruption."""

    def __init__(self, queue_instance: Optional[SpeechQueue] = None, manager_instance: Optional[Any] = None):
        self.queue = queue_instance or speech_queue
        self.voice_mgr = manager_instance or voice_manager

    def handle_interruption(self, session_id: Optional[str] = None) -> VoiceInterruptionPayload:
        active_session = self.voice_mgr._current_session
        s_id = session_id or (active_session.session_id if active_session else "unknown")

        skipped_sentence = self.queue.skip_current()
        cleared_count = self.queue.clear()
        self.queue.cancel()

        if active_session:
            active_session.interruption_count += 1
            # Transition state SPEAKING / THINKING -> INTERRUPTED -> LISTENING
            try:
                if active_session.state != VoiceState.IDLE:
                    self.voice_mgr.transition_state(VoiceState.INTERRUPTED)
                    self.voice_mgr.transition_state(VoiceState.LISTENING)
            except Exception as e:
                logger.warning(f"[InterruptionEngine] Transition warning during interruption: {e}")


        logger.info(f"[InterruptionEngine] Handled user interruption for session '{s_id}'. Cleared {cleared_count} queued items.")

        return VoiceInterruptionPayload(
            session_id=s_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            interrupted_sentence=skipped_sentence
        )


interruption_engine = InterruptionEngine()
