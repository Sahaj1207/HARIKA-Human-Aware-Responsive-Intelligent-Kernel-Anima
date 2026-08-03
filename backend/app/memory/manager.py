import asyncio
from typing import List, Dict, Any, Optional
from app.memory.models import MemoryItem, MemoryCategory, MemoryMetrics
from app.memory.storage import memory_storage, MemoryStorage
from app.memory.long_term import long_term_memory, LongTermMemory
from app.memory.extractor import memory_extractor, MemoryExtractor
from app.memory.retriever import memory_retriever, MemoryRetriever
from app.memory.events import memory_event_bus
from app.core.logging import logger


class MemoryManager:
    """Central Facade Entry Point orchestrating the full Cognitive Memory lifecycle."""

    def __init__(
        self,
        storage: Optional[MemoryStorage] = None,
        long_term: Optional[LongTermMemory] = None,
        extractor: Optional[MemoryExtractor] = None,
        retriever: Optional[MemoryRetriever] = None,
    ):
        self.storage = storage or memory_storage
        self.long_term = long_term or long_term_memory
        self.extractor = extractor or memory_extractor
        self.retriever = retriever or memory_retriever

    def get_memories(
        self,
        query: str = "",
        category: Optional[MemoryCategory] = None,
        user_id: str = "default"
    ) -> List[MemoryItem]:
        all_items = self.storage.load_all(user_id)
        active_items = [item for item in all_items if not item.deleted]

        if category:
            active_items = [item for item in active_items if item.category == category]

        if query:
            return self.retriever.search(query=query, limit=10, user_id=user_id)

        active_items.sort(key=lambda x: (x.importance, x.created_at), reverse=True)
        return active_items[:10]

    def add_memory(self, item: MemoryItem, user_id: str = "default") -> MemoryItem:
        return self.long_term.upsert_item(item, user_id)

    def soft_delete_memory(self, memory_id: str, user_id: str = "default") -> bool:
        return self.long_term.soft_delete(memory_id, user_id)

    def clear_all_memories(self, user_id: str = "default") -> bool:
        for cat in MemoryCategory:
            self.storage.save_category(cat, [], user_id)
        logger.info(f"[MemoryManager] Cleared all memories for user '{user_id}'.")
        return True

    def process_conversation_async(
        self,
        user_message: str,
        assistant_response: str = "",
        user_id: str = "default"
    ) -> None:
        """Asynchronously extracts and persists memory candidates without blocking inference."""
        asyncio.create_task(self._process_extraction_task(user_message, assistant_response, user_id))

    async def _process_extraction_task(
        self,
        user_message: str,
        assistant_response: str,
        user_id: str
    ) -> None:
        try:
            candidates = self.extractor.extract_memories(user_message, assistant_response)
            for candidate in candidates:
                self.add_memory(candidate, user_id)
        except Exception as e:
            logger.error(f"[MemoryManager] Async extraction task error: {e}")

    def get_health_metrics(self, user_id: str = "default") -> MemoryMetrics:
        all_items = self.storage.load_all(user_id)
        active_items = [item for item in all_items if not item.deleted]
        deleted_items = [item for item in all_items if item.deleted]

        category_counts: Dict[str, int] = {cat.value: 0 for cat in MemoryCategory}
        total_importance = 0.0
        total_confidence = 0.0
        latest_ts = "N/A"

        for item in active_items:
            category_counts[item.category.value] = category_counts.get(item.category.value, 0) + 1
            total_importance += item.importance
            total_confidence += item.confidence
            if item.updated_at > latest_ts or latest_ts == "N/A":
                latest_ts = item.updated_at

        count = len(active_items)
        avg_importance = round(total_importance / count, 2) if count > 0 else 0.0
        avg_confidence = round(total_confidence / count, 2) if count > 0 else 0.0
        storage_bytes = self.storage.get_storage_size(user_id)

        return MemoryMetrics(
            total_memories=count,
            categories_count=category_counts,
            deleted_count=len(deleted_items),
            average_importance=avg_importance,
            average_confidence=avg_confidence,
            latest_update=latest_ts,
            storage_bytes=storage_bytes
        )


memory_manager = MemoryManager()
