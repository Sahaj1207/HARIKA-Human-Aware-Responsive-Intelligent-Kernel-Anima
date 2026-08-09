import uuid
import logging
from typing import Dict, Any, Optional, List
import app.voice.providers  # Trigger provider registrations
from app.core.config import settings
from app.voice.schemas import VoiceState, VoiceSession, VoiceContext, VoiceMetrics, LatencyMetrics
from app.voice.base_provider import (
    BaseSpeakerProvider, BaseTranscriberProvider,
    get_speaker_provider_class, get_transcriber_provider_class
)
from app.voice.voice_profile import voice_profile_manager, VoiceProfileManager

logger = logging.getLogger("harika.voice.manager")


class InvalidVoiceStateTransitionError(ValueError):
    """Raised when an illegal voice state transition is attempted."""
    pass


class VoiceManager:
    """Single Public Facade for HARIKA Voice Engine 2.0 dynamically resolving TTS & STT providers."""

    ALLOWED_TRANSITIONS: Dict[VoiceState, set] = {
        VoiceState.IDLE: {VoiceState.LISTENING, VoiceState.THINKING, VoiceState.ERROR},
        VoiceState.LISTENING: {VoiceState.THINKING, VoiceState.IDLE, VoiceState.INTERRUPTED, VoiceState.ERROR},
        VoiceState.THINKING: {VoiceState.SPEAKING, VoiceState.IDLE, VoiceState.INTERRUPTED, VoiceState.ERROR},
        VoiceState.SPEAKING: {VoiceState.LISTENING, VoiceState.IDLE, VoiceState.INTERRUPTED, VoiceState.ERROR},
        VoiceState.INTERRUPTED: {VoiceState.LISTENING, VoiceState.IDLE, VoiceState.ERROR},
        VoiceState.ERROR: {VoiceState.IDLE, VoiceState.LISTENING},
    }

    def __init__(self, profile_manager: Optional[VoiceProfileManager] = None):
        self.profile_manager = profile_manager or voice_profile_manager
        self._current_session: Optional[VoiceSession] = None
        self._context: Optional[VoiceContext] = None

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "subsystem": "VoiceManager",
            "name": "Speech Synthesis & Audio Processing Engine",
            "features": ["Text-to-Speech (TTS)", "Speech-to-Text (STT)", "Real-time Interruption Detection"]
        }

    def _get_speaker(self, provider_override: Optional[str] = None) -> BaseSpeakerProvider:

        name = provider_override or settings.TTS_PROVIDER
        cls = get_speaker_provider_class(name)
        return cls()

    def _get_transcriber(self, provider_override: Optional[str] = None) -> BaseTranscriberProvider:
        name = provider_override or settings.STT_PROVIDER
        cls = get_transcriber_provider_class(name)
        return cls()

    def get_state(self) -> VoiceState:
        return self._current_session.state if self._current_session else VoiceState.IDLE

    def transition_state(self, target_state: VoiceState) -> VoiceState:
        current = self.get_state()
        if current == target_state:
            return current

        allowed = self.ALLOWED_TRANSITIONS.get(current, set())
        if target_state not in allowed:
            err_msg = f"Illegal state transition from '{current}' to '{target_state}'."
            logger.error(f"[VoiceManager] {err_msg}")
            raise InvalidVoiceStateTransitionError(err_msg)

        logger.info(f"[VoiceManager] Voice State Transition: {current} -> {target_state}")
        if self._current_session:
            self._current_session.state = target_state
        return target_state

    def start_session(self, continuous: bool = False, user_id: str = "default") -> VoiceSession:
        session_id = f"vses-{uuid.uuid4().hex[:8]}"
        self._current_session = VoiceSession(
            session_id=session_id,
            state=VoiceState.IDLE
        )
        self._context = VoiceContext(
            session_id=session_id,
            user_id=user_id,
            is_continuous_mode=continuous,
            active_tts_provider=settings.TTS_PROVIDER,
            active_stt_provider=settings.STT_PROVIDER
        )
        self.transition_state(VoiceState.LISTENING)
        logger.info(f"[VoiceManager] Started voice session '{session_id}' (continuous={continuous}).")
        return self._current_session

    def stop_session(self) -> Optional[VoiceSession]:
        if not self._current_session:
            return None
        self.transition_state(VoiceState.IDLE)
        session = self._current_session
        self.save_session_summary_to_memory(session)
        logger.info(f"[VoiceManager] Stopped voice session '{session.session_id}'.")
        return session

    def save_session_summary_to_memory(self, session: VoiceSession) -> None:
        """Stores structured session summary in Cognitive Memory without storing raw audio."""
        try:
            from app.memory.manager import memory_manager
            from app.memory.models import MemoryItem, MemoryCategory
            mem_item = MemoryItem(
                id=f"mem-vses-{uuid.uuid4().hex[:8]}",
                category=MemoryCategory.NOTES,
                title=f"Voice Session Summary: {session.session_id}",
                content=f"Voice Session ({session.session_id}) completed with {session.turn_count} turns, {session.command_count} commands, and {session.interruption_count} interruptions.",
                importance=0.6,
                confidence=0.9,
                source="voice_engine",
                tags=["voice", "voice_session"]
            )
            memory_manager.add_memory(mem_item, user_id=self._context.user_id if self._context else "default")
            logger.info(f"[VoiceManager] Saved session summary for '{session.session_id}' to Cognitive Memory.")
        except Exception as e:
            logger.error(f"[VoiceManager] Error saving voice session memory summary: {e}")

    async def process_voice_directive(
        self,
        voice_text: str,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Processes voice text directives orchestrating Cognition, Tools, Vision, and Agents."""
        import time
        from app.voice.speaker import speaker_coordinator
        from app.tools.manager import tool_manager
        from app.vision.manager import vision_manager
        from app.agents.manager import agent_manager

        t_start = time.time()
        self.transition_state(VoiceState.THINKING)
        response_text = ""
        action_type = "cognition"

        # 1. Vision directive check
        if file_bytes and filename:
            action_type = "vision"
            v_res = vision_manager.process_image(file_bytes, filename, "image/png")
            response_text = f"Visual analysis complete. {v_res.summary}"
        else:
            # 2. Tool directive check
            action_plan = tool_manager.plan_action(voice_text)
            if action_plan.is_tool_action and action_plan.actions:
                action_type = "tool"
                res = await agent_manager.execute_agent_goal(voice_text, user_id=self._context.user_id if self._context else "default")
                response_text = f"Executed directive. Result: {res.get('status')}."
                if self._current_session:
                    self._current_session.command_count += 1
            else:
                # 3. Conversational directive
                response_text = f"I heard: '{voice_text}'. How can I assist further?"

        self.transition_state(VoiceState.SPEAKING)
        stream_res = speaker_coordinator.stream_text_response(response_text)

        if self._current_session:
            self._current_session.turn_count += 1
            self._current_session.latency.end_to_end_latency_ms = round((time.time() - t_start) * 1000, 2)

        return {
            "session_id": self._current_session.session_id if self._current_session else None,
            "action_type": action_type,
            "voice_text": voice_text,
            "response_text": response_text,
            "tts_directive": stream_res.get("current_directive"),
            "latency_ms": round((time.time() - t_start) * 1000, 2)
        }

    def synthesize(self, text: str, provider_override: Optional[str] = None) -> Dict[str, Any]:
        speaker = self._get_speaker(provider_override)
        profile = self.profile_manager.get_profile()
        return speaker.synthesize_speech(text, profile)

    def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav", provider_override: Optional[str] = None) -> str:
        transcriber = self._get_transcriber(provider_override)
        return transcriber.transcribe_audio(audio_bytes, mime_type)

    def health_check(self) -> Dict[str, Any]:
        speaker = self._get_speaker()
        transcriber = self._get_transcriber()
        return {
            "status": "healthy",
            "state": self.get_state().value,
            "speaker": speaker.health_check(),
            "transcriber": transcriber.health_check()
        }


voice_manager = VoiceManager()

