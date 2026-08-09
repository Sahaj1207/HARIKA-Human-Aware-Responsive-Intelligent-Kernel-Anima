import re
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("harika.voice.wakeword")


class WakeWordEngine:
    """Wake-word detection interface ("Hey HARIKA")."""

    def __init__(self, wake_words: Optional[list] = None):
        self.wake_words = wake_words or ["hey harika", "harika", "ok harika"]

    def detect_wake_word(self, text_input: str) -> Tuple[bool, Optional[str]]:
        clean_input = text_input.lower().strip()
        for w in self.wake_words:
            if re.search(r'\b' + re.escape(w) + r'\b', clean_input):
                logger.info(f"[WakeWordEngine] Detected wake word '{w}' in input string.")
                return True, w
        return False, None


wake_word_engine = WakeWordEngine()
