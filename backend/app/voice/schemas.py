from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"


class LatencyMetrics(BaseModel):
    recognition_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tts_generation_latency_ms: float = 0.0
    speech_duration_ms: float = 0.0
    end_to_end_latency_ms: float = 0.0


class VoiceProfile(BaseModel):
    speaking_rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    pause_duration_s: float = 0.5
    greeting_style: str = "friendly"
    emotion_profile: str = "neutral"


class VoiceContext(BaseModel):
    session_id: str
    user_id: str = "default"
    is_continuous_mode: bool = False
    active_tts_provider: str = "browser"
    active_stt_provider: str = "browser"
    start_time: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class VoiceSession(BaseModel):
    session_id: str
    state: VoiceState = VoiceState.IDLE
    turn_count: int = 0
    command_count: int = 0
    interruption_count: int = 0
    summary: str = ""
    latency: LatencyMetrics = Field(default_factory=LatencyMetrics)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VoiceHistoryItem(BaseModel):
    session_id: str
    duration_s: float = 0.0
    turns_count: int = 0
    commands_count: int = 0
    interruptions_count: int = 0
    summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VoiceMetrics(BaseModel):
    total_sessions: int = 0
    average_duration_s: float = 0.0
    total_interruptions: int = 0
    average_recognition_latency_ms: float = 0.0
    average_speech_latency_ms: float = 0.0
    average_e2e_latency_ms: float = 0.0


class VoiceInterruptionPayload(BaseModel):
    session_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    interrupted_sentence: Optional[str] = None
