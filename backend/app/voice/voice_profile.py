import logging
from typing import Dict, Any, Optional
from app.voice.schemas import VoiceProfile

logger = logging.getLogger("harika.voice.voice_profile")


class VoiceProfileManager:
    """Manages voice personality profiles including speaking rate, pitch, volume, and emotion settings."""

    def __init__(self):
        self._active_profile = VoiceProfile(
            speaking_rate=1.0,
            pitch=1.0,
            volume=1.0,
            pause_duration_s=0.5,
            greeting_style="friendly",
            emotion_profile="neutral"
        )

    def get_profile(self) -> VoiceProfile:
        return self._active_profile

    def update_profile(self, **kwargs) -> VoiceProfile:
        data = self._active_profile.model_dump()
        data.update({k: v for k, v in kwargs.items() if v is not None})
        self._active_profile = VoiceProfile(**data)
        logger.info(f"[VoiceProfileManager] Updated voice profile: rate={self._active_profile.speaking_rate}, pitch={self._active_profile.pitch}")
        return self._active_profile


voice_profile_manager = VoiceProfileManager()
