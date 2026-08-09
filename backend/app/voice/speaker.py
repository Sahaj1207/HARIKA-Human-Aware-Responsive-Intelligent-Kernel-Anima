import logging
from typing import Dict, Any, Optional
from app.voice.manager import voice_manager
from app.voice.schemas import VoiceProfile
from app.voice.speech_queue import speech_queue, SpeechQueue

logger = logging.getLogger("harika.voice.speaker")


class SpeakerCoordinator:
    """Coordinates TTS synthesis and streaming speech playback via SpeechQueue."""

    def __init__(self, queue_instance: Optional[SpeechQueue] = None):
        self.queue = queue_instance or speech_queue

    def stream_text_response(self, text_stream: str, provider_override: Optional[str] = None) -> Dict[str, Any]:
        """Receives LLM streaming text chunks, splits into sentences, and queues for instant TTS synthesis."""
        sentences = self.queue.push_text_chunk(text_stream)

        # Synthesize first available sentence for immediate playback
        first_sentence = self.queue.pop_sentence()
        directive = {}
        if first_sentence:
            directive = voice_manager.synthesize(first_sentence, provider_override=provider_override)

        return {
            "queued_sentences": len(sentences),
            "current_directive": directive,
            "queue_remaining": self.queue.queue_size()
        }


speaker_coordinator = SpeakerCoordinator()
