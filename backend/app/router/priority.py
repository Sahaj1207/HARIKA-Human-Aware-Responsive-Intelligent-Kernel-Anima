import logging
from typing import List
from app.router.schemas import EnginePriority, IntentType

from app.router.action_graph import ActionNode, ActionGraph

logger = logging.getLogger("harika.router.priority")


class EnginePriorityResolver:
    """Enforces strict engine priority order (SYSTEM > MEMORY > TOOLS > VISION > PLANNING > AGENTS > VOICE > CHAT)."""

    def resolve_priority(self, graph: ActionGraph) -> ActionGraph:
        conversational_intents = [IntentType.GREETING, IntentType.SOCIAL_CONVERSATION, IntentType.CAPABILITY_QUERY, IntentType.UNKNOWN_INTENT]

        wrappers = [n for n in graph.nodes if n.intent in conversational_intents]
        executables = [n for n in graph.nodes if n.intent not in conversational_intents]


        # Sort executable nodes by priority descending
        executables.sort(key=lambda n: n.priority.value, reverse=True)

        # Conversational wrappers execute first
        graph.nodes = wrappers + executables
        logger.info(f"[PriorityResolver] Prioritized {len(graph.nodes)} action nodes ({len(wrappers)} conversational wrappers first).")
        return graph



priority_resolver = EnginePriorityResolver()
