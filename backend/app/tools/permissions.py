import logging
from typing import Dict, Tuple, Optional
from app.tools.schemas import PermissionLevel, PermissionCachePolicy

logger = logging.getLogger("harika.tools.permissions")


class PermissionEngine:
    """Evaluates security permissions, cache policies, and user authorization requirements."""

    def __init__(self):
        self._permission_cache: Dict[str, PermissionCachePolicy] = {}

    def set_cache_policy(self, tool_name: str, policy: PermissionCachePolicy) -> None:
        self._permission_cache[tool_name.lower()] = policy
        logger.info(f"[PermissionEngine] Set cache policy for '{tool_name}' -> {policy.value}")

    def evaluate(self, tool_name: str, level: PermissionLevel) -> Tuple[bool, bool, str]:
        """
        Evaluates (is_permitted, requires_user_prompt, reason).
        """
        tool_key = tool_name.lower()
        cached_policy = self._permission_cache.get(tool_key)

        if cached_policy == PermissionCachePolicy.ALWAYS_DENY:
            return False, False, "User configured Always Deny for this tool."

        if level == PermissionLevel.NONE:
            return True, False, "No permission required."

        if level == PermissionLevel.LOW or level == PermissionLevel.MEDIUM:
            if cached_policy == PermissionCachePolicy.ALWAYS_ALLOW:
                return True, False, "Cached Always Allow policy active."
            # Default LOW and MEDIUM to allowed with logging
            return True, False, f"Permission granted for {level.value} level."

        if level == PermissionLevel.HIGH:
            # HIGH permission tools always require explicit confirmation
            if cached_policy == PermissionCachePolicy.ALWAYS_ALLOW:
                return True, False, "Cached Always Allow active for High permission tool."
            return True, True, "HIGH risk operation requires user confirmation."

        return True, False, "Permitted"


permission_engine = PermissionEngine()
