import asyncio
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
        description="Launches or closes any application installed on this computer.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["open_application", "close_application"],
        target_aliases={
            "calculator": ["calculator", "calc", "cal", "calculator app"],
            "notepad": ["notepad", "note pad"],
            "chrome": ["chrome", "google chrome"],
            "edge": ["edge", "microsoft edge"],
            "vs code": ["vs code", "vscode", "visual studio code", "code"],
            "cmd": ["cmd", "terminal", "command prompt"],
        },
        operations={"open": "open_application", "close": "close_application"},
        ability="open and close your apps",
        target_description="the name of any installed desktop application (e.g. calculator, notepad, chrome, spotify, vs code)",
    )
    timeout_seconds = 12.0

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

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        canonical, score = super().match_target(requested, operation)
        if score >= 0.9:
            return canonical, score
        from app.tools.system.installed_apps import installed_app_index
        app = installed_app_index.find(requested)
        if app is not None:
            return installed_app_index.normalize(app.name), 0.95
        return canonical, score

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        app_name = args.get("app_name") or args.get("name")
        if not app_name or not isinstance(app_name, str) or not app_name.strip():
            return False, "Application name argument is required."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        app_key = (args.get("app_name") or args.get("name")).strip().lower()
        action = args.get("action", "launch")
        current_os = platform.system().lower()

        if action == "close":
            proc_map = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "cmd": "cmd.exe",
                "terminal": "cmd.exe",
                "command prompt": "cmd.exe",
                "chrome": "chrome.exe",
                "edge": "msedge.exe",
                "vs code": "code.exe",
                "vscode": "code.exe"
            }
            proc_candidates = [proc_map.get(app_key, f"{app_key}.exe")]
            if app_key not in proc_map:
                from app.tools.system.installed_apps import installed_app_index
                installed = installed_app_index.find(app_key)
                if installed is not None:
                    proc_candidates = [f"{name}.exe" for name in installed.process_candidates]
            if app_key == "calculator":
                proc_candidates.insert(0, "CalculatorApp.exe")
            if current_os == "windows":
                try:
                    from app.tools.process_verifier import verify_os_process
                    target_proc = None
                    running_pid = None
                    running_name = None
                    candidate_error = None
                    candidate_name = None
                    for candidate in proc_candidates:
                        running, candidate_pid, candidate_name, candidate_error = verify_os_process(candidate)
                        if running:
                            target_proc = candidate
                            running_pid = candidate_pid
                            running_name = candidate_name
                            break
                    if not target_proc:
                        return {
                            "action": "close",
                            "app_name": app_key,
                            "closed": False,
                            "success": False,
                            "verified": False,
                            "pid": None,
                            "process_name": candidate_name or proc_candidates[-1],
                            "error": candidate_error or f"Process for '{app_key}' was not running."
                        }

                    terminate_args = ["taskkill"]
                    if running_pid:
                        terminate_args.extend(["/PID", str(running_pid)])
                    else:
                        terminate_args.extend(["/IM", target_proc])
                    terminate_args.append("/F")
                    taskkill_result = subprocess.run(
                        terminate_args,
                        capture_output=True,
                        text=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        check=False
                    )
                    if taskkill_result.returncode != 0:
                        return {
                            "action": "close",
                            "app_name": app_key,
                            "closed": False,
                            "success": False,
                            "verified": False,
                            "pid": running_pid,
                            "process_name": running_name or target_proc,
                            "error": taskkill_result.stderr.strip() or taskkill_result.stdout.strip() or f"Failed to terminate '{target_proc}'."
                        }

                    await asyncio.sleep(0.3)
                    still_running, verified_pid, _, verify_error = verify_os_process(target_proc, pid=running_pid, pid_only=True)
                    if still_running:
                        await asyncio.sleep(0.5)
                        still_running, verified_pid, _, verify_error = verify_os_process(target_proc, pid=running_pid, pid_only=True)
                    if still_running and verified_pid == running_pid:
                        return {
                            "action": "close",
                            "app_name": app_key,
                            "closed": False,
                            "success": False,
                            "verified": False,
                            "pid": running_pid,
                            "process_name": running_name or target_proc,
                            "error": f"Process '{target_proc}' is still running after termination was attempted."
                        }
                    if not verify_error or "was not found" not in verify_error.lower():
                        return {
                            "action": "close",
                            "app_name": app_key,
                            "closed": False,
                            "success": False,
                            "verified": False,
                            "pid": running_pid,
                            "process_name": running_name or target_proc,
                            "error": f"Could not verify termination of '{target_proc}': {verify_error or 'process state was inconclusive.'}"
                        }
                    return {
                        "action": "close",
                        "app_name": app_key,
                        "closed": True,
                        "success": True,
                        "verified": True,
                        "pid": running_pid,
                        "process_name": running_name or target_proc,
                        "error": None
                    }
                except Exception as e:
                    return {
                        "action": "close",
                        "app_name": app_key,
                        "closed": False,
                        "success": False,
                        "verified": False,
                        "pid": None,
                        "process_name": proc_candidates[0],
                        "error": f"Failed to terminate application '{app_key}': {str(e)}"
                    }
            return {
                "action": "close",
                "app_name": app_key,
                "closed": False,
                "success": False,
                "verified": False,
                "pid": None,
                "process_name": proc_candidates[0],
                "error": f"Application termination is unsupported on {current_os}."
            }

        if current_os not in self.APP_COMMANDS:

            current_os = "windows"  # Default fallback

        cmd_map = self.APP_COMMANDS.get(current_os, {})
        cmd = cmd_map.get(app_key)

        if not cmd:
            # Never hand an unrecognized name to a shell. Unknown names may only
            # launch through an OS-registered application ID from the index.
            return await self._launch_installed(app_key, current_os, dry_run)

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
                proc = subprocess.Popen(cmd, shell=True)
            else:
                proc = subprocess.Popen(cmd.split())

            # Perform OS level Process Table Verification
            from app.tools.process_verifier import verify_os_process
            await asyncio.sleep(0.3)
            verification_candidates = [app_key]
            if current_os == "windows" and app_key == "calculator":
                verification_candidates = ["CalculatorApp.exe", "calc.exe"]

            verified = False
            found_pid = None
            proc_name = None
            err = None
            for candidate in verification_candidates:
                verified, found_pid, proc_name, err = verify_os_process(candidate, pid=proc.pid)
                if verified:
                    break

            return {
                "app_name": app_key,
                "command": cmd,
                "launched": verified,
                "success": verified,
                "verified": verified,
                "pid": found_pid or proc.pid,
                "process_name": proc_name or app_key,
                "error": err
            }
        except Exception as e:
            return {
                "app_name": app_key,
                "command": cmd,
                "launched": False,
                "success": False,
                "verified": False,
                "pid": None,
                "process_name": app_key,
                "error": f"Failed to launch application '{app_key}': {str(e)}"
            }



    async def _launch_installed(self, app_key: str, current_os: str, dry_run: bool) -> Dict[str, Any]:
        from app.tools.system.installed_apps import installed_app_index
        from app.tools.process_verifier import verify_os_process

        app = installed_app_index.find(app_key) if current_os == "windows" else None
        if app is None:
            return {
                "app_name": app_key,
                "launched": False,
                "success": False,
                "verified": False,
                "pid": None,
                "process_name": None,
                "error": f"'{app_key}' isn't an application I can find installed on this computer",
            }
        if dry_run:
            return {
                "dry_run": True,
                "action": "launch_application",
                "app_name": app.name,
                "app_id": app.app_id,
                "expected_result": f"Launches installed app '{app.name}'",
            }

        # Argument list (no shell); the AppID comes from the OS index, not user text.
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app.app_id}"])
        for _ in range(10):
            await asyncio.sleep(0.5)
            for candidate in app.process_candidates:
                verified, pid, proc_name, _ = verify_os_process(candidate)
                if verified:
                    return {
                        "app_name": app.name,
                        "launched": True,
                        "success": True,
                        "verified": True,
                        "pid": pid,
                        "process_name": proc_name,
                        "error": None,
                    }
        return {
            "app_name": app.name,
            "launched": True,
            "success": True,
            "verified": False,
            "pid": None,
            "process_name": None,
            "error": f"I asked Windows to start {app.name} but couldn't confirm its process is running",
        }


open_application_tool =OpenApplicationTool()
tool_registry.register_tool(open_application_tool)
