from typing import List, Dict, Optional


class ShortTermMemory:
    """Manages active conversation history buffer (20-30 messages max) and session state."""

    def __init__(self, max_messages: int = 25):
        self.max_messages = max_messages
        self.history: List[Dict[str, str]] = []
        self.active_topic: Optional[str] = None
        self.active_task: Optional[str] = None

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_messages:
            self.history.pop(0)

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.history)

    def clear(self) -> None:
        self.history.clear()
        self.active_topic = None
        self.active_task = None


short_term_memory = ShortTermMemory()
