from datetime import datetime, timezone
from typing import List, Optional
from app.memory.models import MemoryItem, MemoryCategory
from app.memory.storage import memory_storage, MemoryStorage
from app.memory.events import memory_event_bus, MemoryEventType
from app.core.logging import logger


class LongTermMemory:
    """Manages persistent deduplicated facts and memory items across all categories."""

    def __init__(self, storage: Optional[MemoryStorage] = None):
        self.storage = storage or memory_storage

    def upsert_item(self, candidate: MemoryItem, user_id: str = "default") -> MemoryItem:
        """
        Inserts a new memory item or updates an existing matching memory item (deduplication).
        """
        items = self.storage.load_category(candidate.category, user_id)
        existing_item: Optional[MemoryItem] = None

        # Duplicate detection by category and title match
        for item in items:
            if not item.deleted and (
                item.title.lower().strip() == candidate.title.lower().strip() or
                item.content.lower().strip() == candidate.content.lower().strip()
            ):
                existing_item = item
                break

        if existing_item:
            # Update existing memory item
            existing_item.content = candidate.content
            existing_item.importance = max(existing_item.importance, candidate.importance)
            existing_item.confidence = min(1.0, existing_item.confidence + 0.05)
            existing_item.revision += 1
            existing_item.updated_at = datetime.now(timezone.utc).isoformat()
            existing_item.last_accessed = datetime.now(timezone.utc).isoformat()
            
            self.storage.save_category(candidate.category, items, user_id)
            memory_event_bus.emit(MemoryEventType.MEMORY_UPDATED, existing_item.model_dump())
            logger.info(f"[LongTermMemory] Deduplicated & Updated Memory: '{existing_item.title}' (Rev {existing_item.revision})")
            return existing_item
        else:
            # Insert new memory item
            items.append(candidate)
            self.storage.save_category(candidate.category, items, user_id)
            memory_event_bus.emit(MemoryEventType.MEMORY_CREATED, candidate.model_dump())
            logger.info(f"[LongTermMemory] Created New Memory: '{candidate.title}' ({candidate.category.value})")
            return candidate

    def soft_delete(self, memory_id: str, user_id: str = "default") -> bool:
        """Applies soft delete (deleted=True) to a memory item."""
        for cat in MemoryCategory:
            items = self.storage.load_category(cat, user_id)
            for item in items:
                if item.id == memory_id and not item.deleted:
                    item.deleted = True
                    item.updated_at = datetime.now(timezone.utc).isoformat()
                    self.storage.save_category(cat, items, user_id)
                    memory_event_bus.emit(MemoryEventType.MEMORY_DELETED, {"id": memory_id, "category": cat.value})
                    logger.info(f"[LongTermMemory] Soft-deleted memory: {memory_id}")
                    return True
        return False


long_term_memory = LongTermMemory()
