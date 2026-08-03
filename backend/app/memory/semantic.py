from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.memory.models import MemoryItem


class BaseVectorIndex(ABC):
    """Abstract Vector Search Index Interface for future Vector DB integrations."""

    @abstractmethod
    async def upsert_vector(self, item: MemoryItem, vector: List[float]) -> None:
        pass

    @abstractmethod
    async def query_similarity(self, query_vector: List[float], top_k: int = 5) -> List[MemoryItem]:
        pass


class SemanticMemory:
    """Vector database abstraction interface placeholder (Chroma/FAISS/Qdrant ready)."""

    def __init__(self, index_provider: BaseVectorIndex = None):
        self.index_provider = index_provider

    def is_vector_db_enabled(self) -> bool:
        return self.index_provider is not None


semantic_memory = SemanticMemory()
