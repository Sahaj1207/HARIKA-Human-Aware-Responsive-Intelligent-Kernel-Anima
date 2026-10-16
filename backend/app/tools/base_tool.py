from abc import ABC, abstractmethod
from difflib import SequenceMatcher
from typing import Dict, Any, Tuple, Optional
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel


class BaseTool(ABC):
    """Abstract Base Class for all HARIKA Tool Plugins."""

    manifest: ToolManifest
    timeout_seconds: float = 10.0

    @abstractmethod
    def health_check(self) -> ToolHealth:
        """Runs health & dependency diagnostics for the tool."""
        pass

    def can_execute(self) -> bool:
        """Returns whether the tool is enabled and health check is available."""
        if not self.manifest.enabled:
            return False
        return self.health_check().available

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates tool arguments prior to execution. Override in plugins."""
        return True, None

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        """Map a natural-language target onto a target this tool owns.

        Returns (canonical_target, score). Free-text operations accept any
        non-empty target as-is; others match their registered targets, allowing
        abbreviations and small typos of at least three characters.
        """
        query = " ".join((requested or "").lower().strip().strip(".,!?/").split())
        if not query:
            return None, 0.0
        if operation is not None and operation in self.manifest.free_text_operations:
            return requested.strip(), 0.6
        best: Tuple[Optional[str], float] = (None, 0.0)
        for canonical, aliases in self.manifest.target_aliases.items():
            for alias in dict.fromkeys([canonical, *aliases]):
                candidate = " ".join(alias.lower().split())
                if query == candidate:
                    return canonical, 1.0
                if len(query) < 3:
                    continue
                if candidate.startswith(query):
                    score = 0.82 + 0.12 * (len(query) / len(candidate))
                else:
                    # Typo/abbreviation tolerance ("calci" ~ "calc", "notpad" ~ "notepad").
                    similarity = SequenceMatcher(None, query, candidate).ratio()
                    score = 0.7 + 0.2 * similarity if similarity >= 0.8 else 0.0
                if score > best[1]:
                    best = (canonical, score)
        return best

    @abstractmethod
    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Executes the tool action or returns dry-run outcome prediction."""
        pass

    def to_schema(self) -> Dict[str, Any]:
        """Returns JSON schema payload for LLM tool discovery."""
        return {
            "name": self.manifest.name,
            "display_name": self.manifest.display_name,
            "description": self.manifest.description,
            "version": self.manifest.version,
            "category": self.manifest.category,
            "permissions": self.manifest.permissions.value,
            "enabled": self.manifest.enabled,
            "platforms": self.manifest.platforms,
            "capabilities": self.manifest.capabilities,
            "target_aliases": self.manifest.target_aliases,
            "operations": self.manifest.operations,
            "free_text_operations": self.manifest.free_text_operations,
        }
