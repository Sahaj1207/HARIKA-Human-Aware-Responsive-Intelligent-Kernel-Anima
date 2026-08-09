import logging
from app.router.schemas import PolicyType, IntentType, RequestContext

logger = logging.getLogger("harika.router.policy")


class PolicyEngine:
    """Selects and enforces routing policies (AUTO, TOOL_FIRST, MEMORY_FIRST, CHAT_ONLY, STRICT_SYSTEM)."""

    def determine_policy(self, intent: IntentType, context: RequestContext) -> PolicyType:
        if intent == IntentType.TOOL_EXECUTION:
            return PolicyType.TOOL_FIRST
        elif intent in [IntentType.MEMORY_STORE, IntentType.MEMORY_QUERY, IntentType.MEMORY_UPDATE]:
            return PolicyType.MEMORY_FIRST
        elif intent == IntentType.SYSTEM_COMMAND:
            return PolicyType.STRICT_SYSTEM
        elif intent == IntentType.CHAT:
            return PolicyType.CHAT_ONLY
        return PolicyType.AUTO


policy_engine = PolicyEngine()
