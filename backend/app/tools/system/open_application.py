import os
import platform
import subprocess
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class OpenApplicationTool(BaseTool):
    """Local Desktop Application Launcher Plugin."""

    manifest = ToolManifest(
        name="open_application",
        display_name="Application Launcher",
        description="Launches local applications (Chrome, Edge, VS Code, Notepad, Calculator) safely.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 5.0

    # Application execution map per OS
    APP_COMMANDS = {
        "windows": {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "chrome": "start chrome",
            "edge": "start msedge",
            "vs code": "code",
            "vscode": "code",
        },
        "darwin": {
            "notepad": "open -a TextEdit",
            "calculator": "open -a Calculator",
            "chrome": "open -a 'Google Chrome'",
            "vs code": "code",
            "vscode": "code",
        },
        "linux": {
            "calculator": "gnome-calculator",
            "chrome": "google-chrome",
            "vs code": "code",
            "vscode": "code",
        }
    }

    def health_check(self) -> ToolHealth:
        current_os = platform.system().lower()
        return ToolHealth(
            available=True,
            reason=f"System OS: {current_os}",
            dependencies=["subprocess"]
        )

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        app_name = args.get("app_name") or args.get("name")
        if not app_name or not isinstance(app_name, str) or not app_name.strip():
            return False, "Application name argument is required."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        app_key = (args.get("app_name") or args.get("name")).strip().lower()
        current_os = platform.system().lower()

        if current_os not in self.APP_COMMANDS:
            current_os = "windows"  # Default fallback

        cmd_map = self.APP_COMMANDS.get(current_os, {})
        cmd = cmd_map.get(app_key)

        if not cmd:
            # Fallback to direct name execution if command map missing
            cmd = app_key

        if dry_run:
            return {
                "dry_run": True,
                "action": "launch_application",
                "app_name": app_key,
                "command": cmd,
                "expected_result": f"Launches desktop app '{app_key}' via command '{cmd}'"
            }

        try:
            if current_os == "windows":
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(cmd.split())

            return {"app_name": app_key, "command": cmd, "launched": True}
        except Exception as e:
            raise RuntimeError(f"Failed to launch application '{app_key}': {e}")


open_application_tool = OpenApplicationTool()
tool_registry.register_tool(open_application_tool)
