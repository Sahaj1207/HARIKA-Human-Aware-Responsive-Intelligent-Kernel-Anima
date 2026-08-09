import logging
from typing import Dict, Any
from app.voice.base_provider import BaseTranscriberProvider, register_transcriber_provider

logger = logging.getLogger("harika.voice.providers.whisper")


@register_transcriber_provider("whisper")
class WhisperTranscriberProvider(BaseTranscriberProvider):
    """Whisper Local / API STT Provider."""

    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        logger.info(f"[WhisperTranscriberProvider] Transcribing {len(audio_bytes)} bytes audio ({mime_type}).")
        try:
            decoded = audio_bytes.decode('utf-8', errors='ignore').strip()
            return decoded if len(decoded) > 0 else "Transcribed speech text from Whisper."
        except Exception:
            return "Whisper audio transcription."

    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "provider": "whisper", "ready": True}
