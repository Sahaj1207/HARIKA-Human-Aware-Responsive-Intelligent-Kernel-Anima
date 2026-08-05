from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False


class ClipboardTool(BaseTool):
    """System Clipboard Read/Write/Clear Manager Plugin."""

    manifest = ToolManifest(
        name="clipboard",
        display_name="Clipboard Service",
        description="Reads, writes, or clears system clipboard text content.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 2.0

    def health_check(self) -> ToolHealth:
        if HAS_PYPERCLIP:
            return ToolHealth(available=True, reason="Pyperclip library active", dependencies=["pyperclip"])
        return ToolHealth(available=False, reason="Pyperclip dependency missing", dependencies=["pyperclip"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action = args.get("action", "read").lower()
        if action not in ["read", "write", "clear"]:
            return False, f"Invalid clipboard action '{action}'. Supported: read, write, clear."
        if action == "write" and "text" not in args:
            return False, "Text argument is required for write action."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        if not HAS_PYPERCLIP:
            raise RuntimeError("Pyperclip module is not installed.")

        action = args.get("action", "read").lower()

        if dry_run:
            return {
                "dry_run": True,
                "action": f"clipboard_{action}",
                "expected_result": f"Executes clipboard {action} operation"
            }

        if action == "read":
            content = pyperclip.paste()
            return {"action": "read", "content": content}
        elif action == "write":
            text = args.get("text", "")
            pyperclip.copy(text)
            return {"action": "write", "text": text, "status": "copied"}
        elif action == "clear":
            pyperclip.copy("")
            return {"action": "clear", "status": "cleared"}

        return {"action": action}


clipboard_tool = ClipboardTool()
tool_registry.register_tool(clipboard_tool)
