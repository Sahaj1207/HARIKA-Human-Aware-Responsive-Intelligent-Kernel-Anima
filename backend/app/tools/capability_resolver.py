from typing import Any, Dict, Iterable, Optional

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


class CapabilityResolver:
    """Resolves normalized goals against registered tool metadata, not phrase branches."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or tool_registry

    def resolve(self, capability: str, target: str, action: str = "launch") -> CapabilityResolution:
        requested = self._normalize(target)
        best = None
        for tool in self.registry.list_tools():
            manifest = tool.manifest
            if capability not in manifest.capabilities and not self._capability_matches(capability, manifest.name):
                continue
            for canonical, aliases in manifest.target_aliases.items():
                for alias in self._unique([canonical, *aliases]):
                    candidate = self._normalize(alias)
                    score = self._match_score(requested, candidate)
                    if score > (best[0] if best else 0.0):
                        best = (score, tool, canonical)

        if best:
            score, tool, canonical = best
            return CapabilityResolution(
                capability=capability,
                action=action,
                target=canonical,
                tool_name=tool.manifest.name,
                confidence=score,
                arguments=self._arguments(tool.manifest.name, action, canonical),
            )

        return CapabilityResolution(
            capability=capability,
            action=action,
            target=requested or None,
            confidence=0.0,
            supported=False,
            reason=f"No registered capability target matched '{target}'.",
        )

    def resolve_open_target(self, target: str) -> CapabilityResolution:
        app = self.resolve("open_application", target, "launch")
        if app.supported:
            return app
        return self.resolve("open_website", target, "open")

    def normalize_node(self, node: Any) -> Any:
        """Normalize a ToolManager action node in-place while preserving its public shape."""
        if node.engine != "ToolManager":
            return node
        raw = node.arguments.get("app_name") or node.arguments.get("target") or self._extract_target(node.arguments.get("query", ""))
        if not raw:
            return node

        if node.action in {"open_app", "close_app", "open_target", "close_target"}:
            is_close = node.action in {"close_app", "close_target"}
            resolution = self.resolve("open_application", raw, "close" if is_close else "launch")
            if not resolution.supported:
                resolution = self.resolve("open_website", raw, "open" if not is_close else "close")
            if resolution.supported:
                if resolution.tool_name == "open_website":
                    node.action = "close_website" if is_close else "open_website"
                    node.arguments = {"target": resolution.target, "query": resolution.target}
                else:
                    node.action = "close_app" if is_close else "open_app"
                    node.arguments = {"app_name": resolution.target, "query": resolution.target, "action": "close" if is_close else "launch"}
        return node

    @staticmethod
    def _capability_matches(capability: str, tool_name: str) -> bool:
        return capability.replace("_", "") in tool_name.replace("_", "")

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").lower().strip().strip(".,!?/").split())

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _match_score(requested: str, candidate: str) -> float:
        if not requested or not candidate:
            return 0.0
        if requested == candidate:
            return 1.0
        if candidate.startswith(requested) or requested.startswith(candidate):
            ratio = min(len(requested), len(candidate)) / max(len(requested), len(candidate))
            return 0.82 + (0.12 * ratio)
        return 0.0

    @staticmethod
    def _arguments(tool_name: str, action: str, target: str) -> Dict[str, Any]:
        if tool_name == "open_application":
            return {"app_name": target, "action": "close" if action == "close" else "launch"}
        return {"target": target}

    @staticmethod
    def _extract_target(query: str) -> str:
        words = (query or "").strip().split()
        if not words:
            return ""
        verbs = {"open", "launch", "start", "run", "bring", "get", "close", "stop", "kill", "terminate", "visit"}
        if words[0].lower() in verbs:
            words = words[1:]
        if words[:2] == ["me", "the"]:
            words = words[2:]
        elif words and words[0].lower() == "the":
            words = words[1:]
        return " ".join(words)


capability_resolver = CapabilityResolver()
