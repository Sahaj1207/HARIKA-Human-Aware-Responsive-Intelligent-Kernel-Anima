import logging
from typing import Dict, Any, Optional
from app.voice.manager import voice_manager

logger = logging.getLogger("harika.voice.transcriber")


class TranscriberCoordinator:
    """Coordinates STT audio transcription requests."""

    def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav", provider_override: Optional[str] = None) -> str:
        logger.info(f"[TranscriberCoordinator] Transcribing audio ({len(audio_bytes)} bytes).")
        return voice_manager.transcribe(audio_bytes, mime_type, provider_override=provider_override)


transcriber_coordinator = TranscriberCoordinator()
