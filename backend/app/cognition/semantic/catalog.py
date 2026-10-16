from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.tools.capability_resolver import CapabilityResolution, CapabilityResolver, operations_of


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
    target_description: str = ""
    free_text: bool = False


class CapabilityCatalog:
    """Read-only normalized view over registered tools and subsystem metadata.

    Resolution is delegated to the same CapabilityResolver that execution uses,
    so the semantic layer can never accept something execution would reject.
    """

    def __init__(self, entries: Iterable[CapabilityCatalogEntry] = (), resolver: Optional[CapabilityResolver] = None):
        self._entries = {entry.capability_id: entry for entry in entries}
        self.resolver = resolver

    @classmethod
    def from_sources(
        cls,
        tool_registry: Any,
        router_registry: Any,
        capability_manager: Optional[Any] = None,
    ) -> "CapabilityCatalog":
        entries: List[CapabilityCatalogEntry] = []
        for tool in tool_registry.list_tools():
            if not tool.manifest.enabled:
                continue
            capabilities = list(getattr(tool.manifest, "capabilities", []) or []) or [tool.manifest.name]
            for capability_id in capabilities:
                entries.append(cls._tool_entry(tool, capability_id))

        for capability in router_registry.get_capabilities():
            entries.extend(cls._router_entries(capability))

        # CapabilityManager only enriches missing IDs with descriptions.
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
        return cls(entries, resolver=CapabilityResolver(tool_registry))

    @staticmethod
    def _tool_entry(tool: Any, capability_id: str) -> CapabilityCatalogEntry:
        manifest = tool.manifest
        action = {
            "open_application": "open_app",
            "close_application": "close_app",
        }.get(capability_id, capability_id)
        operations = [op for op, cap in operations_of(manifest).items() if cap == capability_id] or ["execute"]
        return CapabilityCatalogEntry(
            capability_id=capability_id,
            description=manifest.description,
            supported_operations=operations,
            permissions=manifest.permissions.value,
            platforms=list(manifest.platforms),
            tool_name=manifest.name,
            engine="ToolManager",
            action=action,
            target_aliases=dict(getattr(manifest, "target_aliases", {}) or {}),
            target_description=getattr(manifest, "target_description", "") or "",
            free_text=any(op in (getattr(manifest, "free_text_operations", []) or []) for op in operations),
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

    def describe_operations(self) -> str:
        """Human-readable operation list for the interpreter prompt, built from tool metadata."""
        # One line per tool (not per verb): the prompt stays small and cacheable as tools grow.
        tools: Dict[str, Dict[str, Any]] = {}
        for entry in self._entries.values():
            if entry.engine != "ToolManager" or entry.supported_operations == ["execute"]:
                continue
            tool = tools.setdefault(entry.tool_name or entry.capability_id, {"entry": entry, "operations": []})
            tool["operations"].extend(op for op in entry.supported_operations if op not in tool["operations"])
        lines = []
        for tool in tools.values():
            entry = tool["entry"]
            target = entry.target_description or (
                "one of: " + ", ".join(entry.target_aliases) if entry.target_aliases else "free text"
            )
            operations = ", ".join(f'"{op}"' for op in tool["operations"])
            lines.append(f"- {operations}: {entry.description} Target: {target}.")
        return "\n".join(lines)

    def resolve_action(self, operation: str, target: Optional[str]) -> CapabilityResolution:
        if self.resolver is None:
            return CapabilityResolution(capability=operation, action=operation, supported=False)
        return self.resolver.resolve_operation(operation, target or "")

    def resolve_intent(self, goal: str, operation: str, target: Optional[str]) -> Tuple[Optional[CapabilityCatalogEntry], Optional[str]]:
        """Resolve an LLM target against registered metadata only."""
        if not (target or "").strip():
            return None, None
        resolution = self.resolve_action(operation, target)
        if not resolution.supported:
            return None, None
        return self.get(resolution.capability), resolution.target
