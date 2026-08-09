import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from app.voice.schemas import VoiceProfile

logger = logging.getLogger("harika.voice.base_provider")

_SPEAKER_PROVIDERS: Dict[str, Type["BaseSpeakerProvider"]] = {}
_TRANSCRIBER_PROVIDERS: Dict[str, Type["BaseTranscriberProvider"]] = {}


def register_speaker_provider(name: str):
    def decorator(cls: Type["BaseSpeakerProvider"]):
        _SPEAKER_PROVIDERS[name.lower().strip()] = cls
        logger.info(f"[VoiceRegistry] Registered speaker provider '{name}' -> {cls.__name__}")
        return cls
    return decorator


def register_transcriber_provider(name: str):
    def decorator(cls: Type["BaseTranscriberProvider"]):
        _TRANSCRIBER_PROVIDERS[name.lower().strip()] = cls
        logger.info(f"[VoiceRegistry] Registered transcriber provider '{name}' -> {cls.__name__}")
        return cls
    return decorator


def get_speaker_provider_class(name: str) -> Type["BaseSpeakerProvider"]:
    import app.voice.providers  # Trigger provider registrations
    key = name.lower().strip()
    if key not in _SPEAKER_PROVIDERS:
        logger.warning(f"[VoiceRegistry] Speaker provider '{name}' not found, falling back to 'browser'")
        key = "browser"
    return _SPEAKER_PROVIDERS.get(key, BaseSpeakerProvider)


def get_transcriber_provider_class(name: str) -> Type["BaseTranscriberProvider"]:
    import app.voice.providers  # Trigger provider registrations
    key = name.lower().strip()
    if key not in _TRANSCRIBER_PROVIDERS:
        logger.warning(f"[VoiceRegistry] Transcriber provider '{name}' not found, falling back to 'browser'")
        key = "browser"
    return _TRANSCRIBER_PROVIDERS.get(key, BaseTranscriberProvider)



class BaseSpeakerProvider(ABC):
    """Abstract Interface for Text-To-Speech Providers."""

    @abstractmethod
    def synthesize_speech(self, text: str, profile: Optional[VoiceProfile] = None) -> Dict[str, Any]:
        """Synthesize text into speech audio payload or client instruction."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check provider health and readiness."""
        pass


class BaseTranscriberProvider(ABC):
    """Abstract Interface for Speech-To-Text Providers."""

    @abstractmethod
    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """Transcribe raw audio bytes into text string."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check provider health and readiness."""
        pass
