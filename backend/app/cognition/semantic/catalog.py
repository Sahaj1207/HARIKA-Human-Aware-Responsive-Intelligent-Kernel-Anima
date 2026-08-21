import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field


class CapabilityCatalogEntry(BaseModel):
    capability_id: str
    description: str = ""
    supported_operations: List[str] = Field(default_factory=list)
    argument_schema: Dict[str, Any] = Field(default_factory=dict)
    entity_types: List[str] = Field(default_factory=list)
    permissions: str = "NONE"
    verification_requirements: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    composable_with: List[str] = Field(default_factory=list)
    tool_name: Optional[str] = None
    engine: Optional[str] = None
    action: Optional[str] = None
    target_aliases: Dict[str, List[str]] = Field(default_factory=dict)


class CapabilityCatalog:
    """Read-only normalized view over existing tools and subsystem metadata."""

    def __init__(self, entries: Iterable[CapabilityCatalogEntry] = ()):
        self._entries = {entry.capability_id: entry for entry in entries}

    @classmethod
    def from_sources(
        cls,
        tool_registry: Any,
        router_registry: Any,
        capability_manager: Optional[Any] = None,
    ) -> "CapabilityCatalog":
        entries: List[CapabilityCatalogEntry] = []
        for tool in tool_registry.list_tools():
            manifest = tool.manifest
            capabilities = list(getattr(manifest, "capabilities", []) or [])
            if not capabilities:
                capabilities = [manifest.name]
            for capability_id in capabilities:
                entries.append(cls._tool_entry(tool, capability_id))

        for capability in router_registry.get_capabilities():
            entries.extend(cls._router_entries(capability))

        # CapabilityManager remains an optional source for subsystem descriptions.
        # Its summaries do not expose executable schemas, so they enrich only
        # missing capability IDs and never replace tool metadata.
        if capability_manager is not None:
            for summary in capability_manager.get_all_capabilities():
                subsystem = summary.get("subsystem")
                description = summary.get("name", subsystem or "")
                for feature in summary.get("features", []) or []:
                    capability_id = str(feature)
                    if capability_id not in {entry.capability_id for entry in entries}:
                        entries.append(CapabilityCatalogEntry(
                            capability_id=capability_id,
                            description=description,
                            engine=subsystem,
                        ))
        return cls(entries)

    @staticmethod
    def _tool_entry(tool: Any, capability_id: str) -> CapabilityCatalogEntry:
        manifest = tool.manifest
        action = {
            "open_application": "open_app",
            "close_application": "close_app",
            "open_website": "open_website",
            "close_website": "close_website",
        }.get(capability_id, capability_id)
        operations = list(getattr(manifest, "supported_operations", []) or [])
        if not operations:
            operations = ["execute"]
        return CapabilityCatalogEntry(
            capability_id=capability_id,
            description=manifest.description,
            supported_operations=operations,
            argument_schema=getattr(manifest, "argument_schema", {}) or {},
            entity_types=getattr(manifest, "entity_types", []) or [],
            permissions=manifest.permissions.value,
            verification_requirements=getattr(manifest, "verification_requirements", []) or [],
            platforms=list(manifest.platforms),
            composable_with=getattr(manifest, "composable_with", []) or [],
            tool_name=manifest.name,
            engine="ToolManager",
            action=action,
            target_aliases=dict(getattr(manifest, "target_aliases", {}) or {}),
        )

    @staticmethod
    def _router_entries(capability: Any) -> List[CapabilityCatalogEntry]:
        actions = list(getattr(capability, "actions", []) or [])
        engine = getattr(capability, "engine", None)
        return [CapabilityCatalogEntry(
            capability_id=action,
            description=f"{engine} capability",
            supported_operations=[action],
            engine=engine,
            action=action,
        ) for action in actions]

    def get(self, capability_id: str) -> Optional[CapabilityCatalogEntry]:
        return self._entries.get(capability_id)

    def contains(self, capability_id: str) -> bool:
        return capability_id in self._entries

    def entries(self) -> List[CapabilityCatalogEntry]:
        return list(self._entries.values())

    def as_prompt_payload(self) -> List[Dict[str, Any]]:
        return [entry.model_dump() for entry in self._entries.values()]

    def validate_candidates(self, candidates: Iterable[str]) -> List[str]:
        return [candidate for candidate in candidates if self.contains(candidate)]

    def resolve_intent(self, goal: str, operation: str, target: Optional[str]) -> Tuple[Optional[CapabilityCatalogEntry], Optional[str]]:
        """Resolve an LLM target against registered metadata only."""
        requested = self._normalize(target)
        if not requested:
            return None, None

        goal_words = self._words(goal)
        operation_words = self._words(operation)
        matches = []
        for entry in self._entries.values():
            canonical = self._resolve_target(entry, requested)
            if canonical is None:
                continue
            capability_words = self._words(entry.capability_id) | self._words(entry.action or "")
            goal_score = len(goal_words & capability_words)
            operation_score = int(self._operation_matches(entry, operation_words))
            matches.append((goal_score + operation_score, goal_score, operation_score, entry, canonical))

        if not matches:
            return None, None
        matches.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        _, goal_score, operation_score, entry, canonical = matches[0]
        if goal_score == 0 and operation_score == 0:
            return None, None
        return entry, canonical

    @classmethod
    def _resolve_target(cls, entry: CapabilityCatalogEntry, requested: str) -> Optional[str]:
        for canonical, aliases in entry.target_aliases.items():
            candidates = [canonical, *aliases]
            if requested in {cls._normalize(value) for value in candidates}:
                return canonical
        return None

    @staticmethod
    def _operation_matches(entry: CapabilityCatalogEntry, operation_words: set[str]) -> bool:
        if operation_words == {"execute"} and entry.action not in (None, "execute"):
            return False
        supported = set()
        for value in entry.supported_operations:
            supported.update(CapabilityCatalog._words(value))
        action_words = CapabilityCatalog._words(entry.action or "")
        return bool(operation_words & (supported | action_words))

    @staticmethod
    def _normalize(value: Optional[str]) -> str:
        return " ".join((value or "").lower().strip().split())

    @staticmethod
    def _words(value: Optional[str]) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", (value or "").lower()))
