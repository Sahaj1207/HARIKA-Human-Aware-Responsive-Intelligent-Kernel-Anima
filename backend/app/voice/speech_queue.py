import re
import queue
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("harika.voice.speech_queue")


class SpeechQueue:
    """Manages sentence queuing, streaming playback pacing, skipping, and cancellation to eliminate overlapping speech."""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._current_sentence: Optional[str] = None
        self._is_cancelled: bool = False

    def push_text_chunk(self, text_chunk: str) -> List[str]:
        if self._is_cancelled:
            return []

        # Split on sentence boundaries (. ! ?)
        sentences = re.split(r'(?<=[.!?])\s+', text_chunk.strip())
        added = []
        for s in sentences:
            s_clean = s.strip()
            if s_clean:
                self._queue.put(s_clean)
                added.append(s_clean)
                logger.info(f"[SpeechQueue] Queued sentence ({len(s_clean)} chars): '{s_clean[:30]}...'")
        return added

    def pop_sentence(self) -> Optional[str]:
        if self._is_cancelled or self._queue.empty():
            return None
        self._current_sentence = self._queue.get()
        return self._current_sentence

    def skip_current(self) -> Optional[str]:
        skipped = self._current_sentence
        self._current_sentence = None
        logger.info(f"[SpeechQueue] Skipped current sentence: '{skipped}'")
        return skipped

    def clear(self) -> int:
        count = self._queue.qsize()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._current_sentence = None
        self._is_cancelled = False
        logger.info(f"[SpeechQueue] Cleared speech queue ({count} items removed).")
        return count

    def cancel(self) -> None:
        self._is_cancelled = True
        self.clear()
        logger.info("[SpeechQueue] Cancelled speech queue.")

    def is_empty(self) -> bool:
        return self._queue.empty() and self._current_sentence is None

    def queue_size(self) -> int:
        return self._queue.qsize()


speech_queue = SpeechQueue()
