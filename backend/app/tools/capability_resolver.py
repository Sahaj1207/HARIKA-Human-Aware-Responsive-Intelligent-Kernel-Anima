from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.tools.registry import ToolRegistry, tool_registry


class CapabilityResolution(BaseModel):
    capability: str
    action: str
    target: Optional[str] = None
    tool_name: Optional[str] = None
    confidence: float = 0.0
    arguments: Dict[str, Any] = Field(default_factory=dict)
    supported: bool = True
    reason: Optional[str] = None


# Router node actions that predate generic capabilities; kept for API compatibility.
_LEGACY_NODE_ACTIONS = {
    "open_application": "open_app",
    "close_application": "close_app",
    "open_website": "open_website",
    "close_website": "close_website",
}


def operations_of(manifest: Any) -> Dict[str, str]:
    """Declared verb -> capability map, inferring "open_application" -> "open" for older manifests."""
    declared = dict(getattr(manifest, "operations", {}) or {})
    if declared:
        return declared
    inferred: Dict[str, str] = {}
    for capability in getattr(manifest, "capabilities", []) or []:
        verb = capability.split("_", 1)[0]
        if "_" in capability:
            inferred.setdefault(verb, capability)
    return inferred


class CapabilityResolver:
    """Resolves (operation, target) against registered tool metadata, not phrase branches."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or tool_registry

    def resolve_operation(self, operation: str, target: str) -> CapabilityResolution:
        """Pick the tool whose declared operation and own target matching fit best."""
        operation = (operation or "").strip().lower()
        best = None
        for tool in self.registry.list_tools():
            manifest = tool.manifest
            operations = operations_of(manifest)
            if not manifest.enabled or operation not in operations:
                continue
            canonical, score = tool.match_target(target, operation)
            if canonical and score > (best[0] if best else 0.0):
                best = (score, tool, canonical)
        if best is None:
            return CapabilityResolution(
                capability=operation,
                action=operation,
                target=self._normalize(target) or None,
                supported=False,
                reason=f"No registered capability can {operation or 'handle'} '{target}'.",
            )
        score, tool, canonical = best
        capability = operations_of(tool.manifest)[operation]
        return CapabilityResolution(
            capability=capability,
            action=operation,
            target=canonical,
            tool_name=tool.manifest.name,
            confidence=score,
            arguments=self._arguments(tool.manifest.name, capability, operation, canonical),
        )

    def resolve(self, capability: str, target: str, action: str = "launch") -> CapabilityResolution:
        """Resolve a target for one specific capability."""
        best = None
        for tool in self.registry.list_tools():
            manifest = tool.manifest
            if capability not in manifest.capabilities and not self._capability_matches(capability, manifest.name):
                continue
            operation = next((op for op, cap in operations_of(manifest).items() if cap == capability), None)
            canonical, score = tool.match_target(target, operation)
            if canonical and score > (best[0] if best else 0.0):
                best = (score, tool, canonical)

        if best:
            score, tool, canonical = best
            return CapabilityResolution(
                capability=capability,
                action=action,
                target=canonical,
                tool_name=tool.manifest.name,
                confidence=score,
                arguments=self._arguments(tool.manifest.name, capability, action, canonical),
            )

        return CapabilityResolution(
            capability=capability,
            action=action,
            target=self._normalize(target) or None,
            confidence=0.0,
            supported=False,
            reason=f"No registered capability target matched '{target}'.",
        )

    def resolve_open_target(self, target: str) -> CapabilityResolution:
        return self.resolve_operation("open", target)

    def apply_to_node(self, node: Any, resolution: CapabilityResolution, operation: str, extra: Optional[Dict[str, Any]] = None) -> Any:
        """Write a supported resolution onto a router ActionNode."""
        query = node.arguments.get("query") or resolution.target
        node.action = _LEGACY_NODE_ACTIONS.get(resolution.capability, resolution.capability)
        arguments = dict(extra or {})
        arguments.update(resolution.arguments)
        arguments.update({"query": query, "operation": operation, "resolution_confidence": resolution.confidence})
        node.arguments = arguments
        return node

    def normalize_node(self, node: Any) -> Any:
        """Resolve a generic open/close ToolManager node in place; unresolved nodes are left as-is."""
        if node.engine != "ToolManager" or node.action not in {"open_target", "close_target", "open_app", "close_app"}:
            return node
        raw = node.arguments.get("app_name") or node.arguments.get("target") or ""
        if not raw:
            return node
        operation = "close" if node.action in {"close_target", "close_app"} else "open"
        resolution = self.resolve_operation(operation, raw)
        if resolution.supported:
            self.apply_to_node(node, resolution, operation)
        return node

    def is_semantic_capability(self, action: Optional[str]) -> bool:
        """Whether a node action is one the semantic interpreter can express via an operation."""
        declared = set()
        for tool in self.registry.list_tools():
            declared.update(operations_of(tool.manifest).values())
        declared.update(_LEGACY_NODE_ACTIONS[c] for c in list(declared) if c in _LEGACY_NODE_ACTIONS)
        return action in declared or action in {"open_target", "close_target"}

    @staticmethod
    def is_resolved(node: Any) -> bool:
        return not (node.engine == "ToolManager" and node.action in {"open_target", "close_target"})

    @staticmethod
    def _capability_matches(capability: str, tool_name: str) -> bool:
        return capability.replace("_", "") in tool_name.replace("_", "")

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").lower().strip().strip(".,!?/").split())

    @staticmethod
    def _arguments(tool_name: str, capability: str, operation: str, target: str) -> Dict[str, Any]:
        if tool_name == "open_application":
            return {"app_name": target, "action": "close" if operation == "close" or capability == "close_application" else "launch"}
        return {"target": target}


capability_resolver = CapabilityResolver()
