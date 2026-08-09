import time
import logging
from typing import Dict, Any, Optional
from app.presence.schemas import WorkspaceItem

logger = logging.getLogger("harika.presence.workspace")


class WorkspaceManager:
    """Manages temporary conversational workspace items with automatic expiration."""

    def __init__(self, default_ttl: float = 600.0):
        self._workspace: Dict[str, WorkspaceItem] = {}
        self.default_ttl = default_ttl

    def set_item(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        item = WorkspaceItem(key=key, value=value, ttl_seconds=ttl)
        self._workspace[key] = item
        logger.info(f"[WorkspaceManager] Set workspace item '{key}' (TTL={ttl}s).")

    def get_item(self, key: str) -> Optional[Any]:
        self._purge_stale()
        item = self._workspace.get(key)
        return item.value if item else None

    def get_all(self) -> Dict[str, Any]:
        self._purge_stale()
        return {k: item.value for k, item in self._workspace.items()}

    def clear(self) -> None:
        self._workspace.clear()

    def _purge_stale(self) -> None:
        now = time.time()
        stale_keys = [
            k for k, item in self._workspace.items()
            if (now - item.created_at) > item.ttl_seconds
        ]
        for k in stale_keys:
            del self._workspace[k]
            logger.info(f"[WorkspaceManager] Expired stale workspace item '{k}'.")


workspace_manager = WorkspaceManager()
