import logging
from typing import Dict, Any, Optional
from app.presence.workspace import workspace_manager, WorkspaceManager
from app.presence.schemas import ConversationState

logger = logging.getLogger("harika.presence.context_awareness")


class ContextAwarenessEngine:
    """Resolves ambiguous references ('continue', 'do that', 'fix it', 'open it', 'remember that') using conversation state & workspace."""

    def resolve_reference(
        self,
        message: str,
        state: Optional[ConversationState] = None,
        workspace: Optional[WorkspaceManager] = None
    ) -> Dict[str, Any]:
        clean = message.lower().strip()
        ws = workspace or workspace_manager

        if clean in ["continue", "proceed", "keep going", "next step"]:
            task = state.current_task if state else None
            agent = state.current_goal if state else None
            resolved = task or agent or ws.get_item("current_plan") or "active_task"
            logger.info(f"[ContextAwareness] Resolved 'continue' to target: {resolved}")
            return {"action": "continue_task", "target": resolved}

        if "remember that" in clean or "save that" in clean:
            last_disc = ws.get_item("current_discussion")
            logger.info(f"[ContextAwareness] Resolved 'remember that' to discussion: {last_disc}")
            return {"action": "store_memory", "content": last_disc or message}

        if "open it" in clean:
            last_file = ws.get_item("current_file")
            logger.info(f"[ContextAwareness] Resolved 'open it' to file: {last_file}")
            return {"action": "open_file", "target": last_file or "workspace"}

        return {"action": "none", "target": message}


context_awareness_engine = ContextAwarenessEngine()
