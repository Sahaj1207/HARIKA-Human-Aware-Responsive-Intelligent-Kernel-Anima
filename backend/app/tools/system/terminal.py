import re
import subprocess
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry


class TerminalTool(BaseTool):
    """Sandboxed Safe Whitelisted CLI Terminal Command Runner Plugin."""

    manifest = ToolManifest(
        name="terminal",
        display_name="Terminal Sandbox Engine",
        description="Executes whitelisted safe CLI commands (pwd, dir, ls, whoami, echo, python --version, git status).",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.HIGH,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 5.0

    WHITELIST_PATTERNS = [
        r"^pwd$",
        r"^dir$",
        r"^ls$",
        r"^whoami$",
        r"^echo\s+.*$",
        r"^python\s+--version$",
        r"^git\s+status$",
    ]

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Command Whitelist Sandbox active", dependencies=["subprocess"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        cmd = args.get("command")
        if not cmd or not isinstance(cmd, str) or not cmd.strip():
            return False, "Command argument is required."

        clean_cmd = cmd.strip().lower()

        # Reject dangerous command chaining operators
        if any(op in clean_cmd for op in ['&', '|', ';', '>', '<', '`', '$']):
            return False, f"Command chaining and redirection operators ('&', '|', ';', '>') are strictly prohibited."

        # Check against whitelist patterns
        matched = False
        for pattern in self.WHITELIST_PATTERNS:
            if re.match(pattern, clean_cmd):
                matched = True
                break

        if not matched:
            return False, f"Command '{cmd}' is not in the safe command whitelist. Allowed: pwd, dir, ls, whoami, echo, python --version, git status."

        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        cmd = args["command"].strip()

        if dry_run:
            return {
                "dry_run": True,
                "action": "execute_terminal_command",
                "command": cmd,
                "expected_result": f"Executes whitelisted CLI command '{cmd}'"
            }

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            return {
                "command": cmd,
                "exit_code": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Terminal command '{cmd}' timed out after {self.timeout_seconds}s.")


terminal_tool = TerminalTool()
tool_registry.register_tool(terminal_tool)
