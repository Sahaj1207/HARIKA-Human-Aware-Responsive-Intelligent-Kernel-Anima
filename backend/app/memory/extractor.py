import re
import uuid
from typing import List, Dict
from app.memory.models import MemoryItem, MemoryCategory
from app.memory.importance import importance_engine


class MemoryExtractor:
    """Parses conversation turns to extract structured candidate memory items."""

    PREFERENCE_PATTERNS = [
        (r"(?:my favorite|i love|i prefer|i like)\s+([a-zA-Z0-9_\-\s]+)", "User Preference", MemoryCategory.PREFERENCES),
        (r"(?:my name is|call me)\s+([a-zA-Z0-9_\-]+)", "User Name", MemoryCategory.USER_PROFILE),
        (r"(?:current project|working on|building)\s+([a-zA-Z0-9_\-\s]+)", "Active Project", MemoryCategory.PROJECTS),
        (r"(?:my goal is|aiming to|want to)\s+([a-zA-Z0-9_\-\s]+)", "User Goal", MemoryCategory.GOALS),
    ]

    def extract_memories(self, user_message: str, assistant_response: str = "") -> List[MemoryItem]:
        candidates: List[MemoryItem] = []
        clean_msg = user_message.strip()

        for pattern, default_title, category in self.PREFERENCE_PATTERNS:
            match = re.search(pattern, clean_msg, re.IGNORECASE)
            if match:
                matched_val = match.group(1).strip()
                content_str = f"{default_title}: {matched_val}"
                importance, confidence = importance_engine.evaluate(clean_msg, category.value)

                if importance >= 0.5:
                    item = MemoryItem(
                        id=f"mem-{uuid.uuid4().hex[:8]}",
                        category=category,
                        title=f"{default_title}",
                        content=matched_val,
                        importance=importance,
                        confidence=confidence,
                        source="extractor",
                        tags=[category.value, "conversation_extracted"],
                    )
                    candidates.append(item)

        return candidates


memory_extractor = MemoryExtractor()
