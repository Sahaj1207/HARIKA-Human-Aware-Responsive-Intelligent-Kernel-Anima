import time
import logging
from typing import Dict, Any, Optional
from app.voice.schemas import VoiceSession, VoiceState
from app.voice.manager import voice_manager

logger = logging.getLogger("harika.voice.conversation")


class ConversationEngine:
    """Manages single interaction vs continuous conversation mode, timeouts, and session turn tracking."""

    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds
        self._last_active_time: float = time.time()

    def start_conversation(self, continuous: bool = False, user_id: str = "default") -> VoiceSession:
        self._last_active_time = time.time()
        session = voice_manager.start_session(continuous=continuous, user_id=user_id)
        logger.info(f"[ConversationEngine] Started conversation mode (continuous={continuous}).")
        return session

    def record_turn(self, user_input: str, assistant_response: str) -> None:
        self._last_active_time = time.time()
        session = voice_manager._current_session
        if session:
            session.turn_count += 1
            logger.info(f"[ConversationEngine] Turn {session.turn_count} recorded for session '{session.session_id}'.")

    def check_timeout(self) -> bool:
        session = voice_manager._current_session
        if not session or session.state == VoiceState.IDLE:
            return False

        elapsed = time.time() - self._last_active_time
        if elapsed > self.timeout_seconds:
            logger.info(f"[ConversationEngine] Conversation timeout reached ({elapsed:.1f}s > {self.timeout_seconds}s). Resetting to IDLE.")
            voice_manager.stop_session()
            return True
        return False


conversation_engine = ConversationEngine()
