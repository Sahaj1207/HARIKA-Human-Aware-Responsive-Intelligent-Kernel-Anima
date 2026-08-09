import logging
from typing import Dict, Any, Optional
from app.core.config import settings
from app.voice.base_provider import BaseSpeakerProvider, register_speaker_provider
from app.voice.schemas import VoiceProfile

logger = logging.getLogger("harika.voice.providers.elevenlabs")


@register_speaker_provider("elevenlabs")
class ElevenLabsSpeakerProvider(BaseSpeakerProvider):
    """ElevenLabs Cloud TTS Provider (Optional cloud provider)."""

    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"

    def synthesize_speech(self, text: str, profile: Optional[VoiceProfile] = None) -> Dict[str, Any]:
        if not self.api_key:
            logger.warning("[ElevenLabsSpeakerProvider] API key missing. Falling back to Browser TTS instructions.")
            prof = profile or VoiceProfile()
            return {
                "provider": "elevenlabs_fallback",
                "type": "browser_tts_directive",
                "text": text,
                "rate": prof.speaking_rate,
                "status": "fallback"
            }

        # Structure payload for ElevenLabs API integration
        return {
            "provider": "elevenlabs",
            "type": "audio_stream_url",
            "endpoint": f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            "text": text,
            "voice_id": self.voice_id,
            "status": "ready"
        }

    def health_check(self) -> Dict[str, Any]:
        has_key = bool(self.api_key)
        return {
            "status": "healthy" if has_key else "unconfigured",
            "provider": "elevenlabs",
            "ready": has_key
        }
