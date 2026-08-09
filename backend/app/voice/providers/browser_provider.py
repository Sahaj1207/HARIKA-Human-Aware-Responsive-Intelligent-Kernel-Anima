import logging
from typing import Dict, Any, Optional
from app.voice.base_provider import BaseSpeakerProvider, BaseTranscriberProvider, register_speaker_provider, register_transcriber_provider
from app.voice.schemas import VoiceProfile

logger = logging.getLogger("harika.voice.providers.browser")


@register_speaker_provider("browser")
class BrowserSpeakerProvider(BaseSpeakerProvider):
    """Default Browser Web Speech Synthesis TTS Provider."""

    def synthesize_speech(self, text: str, profile: Optional[VoiceProfile] = None) -> Dict[str, Any]:
        prof = profile or VoiceProfile()
        return {
            "provider": "browser",
            "type": "browser_tts_directive",
            "text": text,
            "rate": prof.speaking_rate,
            "pitch": prof.pitch,
            "volume": prof.volume,
            "status": "ready"
        }

    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "provider": "browser", "ready": True}


@register_transcriber_provider("browser")
class BrowserTranscriberProvider(BaseTranscriberProvider):
    """Default Browser Web Speech Recognition STT Provider."""

    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        # Browser STT handles recognition client-side via Web Speech API
        try:
            return audio_bytes.decode('utf-8', errors='ignore').strip()
        except Exception:
            return "Speech audio input received."

    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "provider": "browser", "ready": True}
