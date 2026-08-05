import logging
from typing import Dict, List, Optional
from app.tools.base_tool import BaseTool

logger = logging.getLogger("harika.tools.registry")


class ToolRegistry:
    """Central Plugin Container managing Tool Registration & Auto-Discovery."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        name = tool.manifest.name.lower()
        self._tools[name] = tool
        logger.info(f"[ToolRegistry] Registered Tool Plugin: '{tool.manifest.display_name}' ({name})")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name.lower().strip())

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def toggle_tool(self, name: str, enabled: bool) -> bool:
        tool = self.get_tool(name)
        if tool:
            tool.manifest.enabled = enabled
            logger.info(f"[ToolRegistry] Toggled Tool '{name}' enabled={enabled}")
            return True
        return False


tool_registry = ToolRegistry()
