import json
import os
from pathlib import Path
from typing import List, Dict, Any
from app.memory.models import MemoryItem, MemoryCategory
from app.core.logging import logger
from app.core.paths import data_path


class MemoryStorage:
    """Thread-safe JSON persistence storage engine targeting multi-user directory layout."""

    def __init__(self, base_dir: str = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # Default storage path: backend/data/memory/users/
            self.base_dir = data_path("memory", "users")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_dir(self, user_id: str = "default") -> Path:
        user_dir = self.base_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _get_category_file(self, category: MemoryCategory, user_id: str = "default") -> Path:
        user_dir = self._get_user_dir(user_id)
        filename = f"{category.value}.json"
        return user_dir / filename

    def load_category(self, category: MemoryCategory, user_id: str = "default") -> List[MemoryItem]:
        file_path = self._get_category_file(category, user_id)
        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [MemoryItem(**item) for item in data]
        except Exception as e:
            logger.error(f"Error reading memory category file {file_path}: {e}")
            return []

    def save_category(self, category: MemoryCategory, items: List[MemoryItem], user_id: str = "default") -> None:
        file_path = self._get_category_file(category, user_id)
        try:
            serialized = [item.model_dump() for item in items]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving memory category file {file_path}: {e}")

    def load_all(self, user_id: str = "default") -> List[MemoryItem]:
        all_items: List[MemoryItem] = []
        for cat in MemoryCategory:
            all_items.extend(self.load_category(cat, user_id))
        return all_items

    def get_storage_size(self, user_id: str = "default") -> int:
        user_dir = self._get_user_dir(user_id)
        total_size = 0
        for path in user_dir.glob("*.json"):
            if path.is_file():
                total_size += path.stat().st_size
        return total_size


memory_storage = MemoryStorage()
