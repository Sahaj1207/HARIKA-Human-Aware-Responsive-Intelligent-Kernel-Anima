import uuid
from datetime import datetime, timezone
from typing import List, Optional
from app.memory.models import MemoryItem, MemoryCategory
from app.memory.storage import memory_storage, MemoryStorage
from app.memory.events import memory_event_bus, MemoryEventType
from app.core.logging import logger


class EpisodicMemory:
    """Manages timeline event logs and episodic experience milestones."""

    def __init__(self, storage: Optional[MemoryStorage] = None):
        self.storage = storage or memory_storage

    def record_episode(self, title: str, description: str, user_id: str = "default") -> MemoryItem:
        items = self.storage.load_category(MemoryCategory.EPISODES, user_id)
        
        episode = MemoryItem(
            id=f"ep-{uuid.uuid4().hex[:8]}",
            category=MemoryCategory.EPISODES,
            title=title,
            content=description,
            importance=0.75,
            confidence=0.95,
            source="system",
            tags=["episode", "milestone"],
        )
        
        items.append(episode)
        self.storage.save_category(MemoryCategory.EPISODES, items, user_id)
        memory_event_bus.emit(MemoryEventType.MEMORY_CREATED, episode.model_dump())
        logger.info(f"[EpisodicMemory] Recorded Episode: '{title}'")
        return episode

    def get_recent_episodes(self, limit: int = 5, user_id: str = "default") -> List[MemoryItem]:
        items = self.storage.load_category(MemoryCategory.EPISODES, user_id)
        active_items = [item for item in items if not item.deleted]
        active_items.sort(key=lambda x: x.created_at, reverse=True)
        return active_items[:limit]


episodic_memory = EpisodicMemory()
