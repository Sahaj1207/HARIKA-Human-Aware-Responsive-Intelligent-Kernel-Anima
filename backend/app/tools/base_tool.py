from abc import ABC, abstractmethod
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
        }
