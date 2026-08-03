from typing import List, Optional
from app.memory.models import MemoryItem, MemoryQuery
from app.memory.storage import memory_storage, MemoryStorage
from app.memory.events import memory_event_bus, MemoryEventType


class MemoryRetriever:
    """Ranks and retrieves top relevant memories for prompt context injection."""

    def __init__(self, storage: Optional[MemoryStorage] = None):
        self.storage = storage or memory_storage

    def search(self, query: str = "", limit: int = 10, user_id: str = "default") -> List[MemoryItem]:
        """
        Public search abstraction returning up to 10 top relevant, high importance memories.
        """
        all_items = self.storage.load_all(user_id)
        # Filter active non-deleted items
        active_items = [item for item in all_items if not item.deleted]

        if not query or not query.strip():
            # If no query string, rank purely by importance and recency
            active_items.sort(key=lambda x: (x.importance, x.created_at), reverse=True)
            results = active_items[:limit]
            memory_event_bus.emit(MemoryEventType.MEMORY_RETRIEVED, {"count": len(results), "query": "all"})
            return results

        clean_q = query.lower().strip()
        keywords = clean_q.split()

        scored_items = []
        for item in active_items:
            content_lower = item.content.lower()
            title_lower = item.title.lower()
            tags_lower = " ".join(item.tags).lower()

            relevance_score = 0.0
            for kw in keywords:
                if kw in title_lower:
                    relevance_score += 0.5
                if kw in content_lower:
                    relevance_score += 0.3
                if kw in tags_lower:
                    relevance_score += 0.2

            final_score = relevance_score + (item.importance * 0.5)
            if final_score > 0.1:
                scored_items.append((final_score, item))

        scored_items.sort(key=lambda x: (x[0], x[1].created_at), reverse=True)
        results = [item for _, item in scored_items[:limit]]
        
        memory_event_bus.emit(MemoryEventType.MEMORY_RETRIEVED, {"count": len(results), "query": query})
        return results


memory_retriever = MemoryRetriever()
