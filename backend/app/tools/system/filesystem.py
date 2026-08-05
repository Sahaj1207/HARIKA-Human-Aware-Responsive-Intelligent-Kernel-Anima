import os
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class FilesystemTool(BaseTool):
    """Sandboxed Local Filesystem Manager Plugin."""

    manifest = ToolManifest(
        name="filesystem",
        display_name="Filesystem Manager",
        description="Safely creates folders, lists directory files, reads, and writes files within allowed workspace paths.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.MEDIUM,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 5.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Path Sandbox active", dependencies=["os", "pathlib"])

    def _is_path_allowed(self, target_path: Path) -> bool:
        try:
            resolved = target_path.resolve()
        except Exception:
            return False

        resolved_str = str(resolved).lower()

        # Explicitly block system root paths
        blocked = ["system32", "windows", "program files", "program files (x86)"]
        if any(b in resolved_str for b in blocked):
            return False

        # Block root drive direct access (e.g. C:\)
        if len(resolved.parts) <= 1:
            return False

        # Check if inside any allowed directory
        user_home = Path.home()
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        allowed_dirs = [
            user_home / "Documents",
            user_home / "Desktop",
            user_home / "Downloads",
            project_root,
        ]

        for allowed in allowed_dirs:
            try:
                resolved.relative_to(allowed.resolve())
                return True
            except ValueError:
                continue

        return False

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action = args.get("action", "list_files").lower()
        path_str = args.get("path")

        if not path_str or not isinstance(path_str, str) or not path_str.strip():
            return False, "Path argument is required."

        target_path = Path(path_str.strip())
        if not self._is_path_allowed(target_path):
            return False, f"Access denied. Path '{path_str}' is outside allowed sandbox locations (Documents, Desktop, Downloads, Workspace)."

        if action in ["read_file", "write_file"] and target_path.exists() and target_path.is_dir():
            return False, f"Target path '{path_str}' is a directory, not a file."

        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        action = args.get("action", "list_files").lower()
        target_path = Path(args["path"].strip()).resolve()

        if dry_run:
            return {
                "dry_run": True,
                "action": f"filesystem_{action}",
                "path": str(target_path),
                "expected_result": f"Executes filesystem {action} on {target_path}"
            }

        if action == "create_folder":
            target_path.mkdir(parents=True, exist_ok=True)
            return {"action": "create_folder", "path": str(target_path), "created": True}

        elif action == "list_files":
            if not target_path.exists():
                raise FileNotFoundError(f"Directory '{target_path}' does not exist.")
            items = [p.name for p in target_path.iterdir()]
            return {"action": "list_files", "path": str(target_path), "count": len(items), "files": items[:50]}

        elif action == "read_file":
            if not target_path.exists():
                raise FileNotFoundError(f"File '{target_path}' does not exist.")
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read(5000)
            return {"action": "read_file", "path": str(target_path), "content": content}

        elif action == "write_file":
            overwrite = args.get("overwrite", False)
            if target_path.exists() and not overwrite:
                raise FileExistsError(f"File '{target_path}' already exists. Pass overwrite=True to replace.")
            content = args.get("content", "")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"action": "write_file", "path": str(target_path), "bytes_written": len(content)}

        return {"action": action, "path": str(target_path)}


filesystem_tool = FilesystemTool()
tool_registry.register_tool(filesystem_tool)
