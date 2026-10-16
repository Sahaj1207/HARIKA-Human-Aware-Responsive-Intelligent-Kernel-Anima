import asyncio
import ctypes
import os
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

# Windows virtual-key codes for media keys.
_MEDIA_KEYS = {"pause": 0xB3, "resume": 0xB3, "next": 0xB0, "previous": 0xB1}
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_POWER_DELAY_SECONDS = 60


class SystemControlTool(BaseTool):
    """Volume, brightness, media keys, power and screenshots through fixed OS calls."""

    manifest = ToolManifest(
        name="system_control",
        display_name="System Controls",
        description="Controls volume, screen brightness, media playback, screenshots, and locking, sleeping, shutting down or restarting the computer.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "darwin"],
        capabilities=["set_level", "adjust_level", "mute_audio", "media_control", "power_control", "take_screenshot"],
        operations={
            "set": "set_level", "increase": "adjust_level", "decrease": "adjust_level",
            "mute": "mute_audio", "unmute": "mute_audio",
            "pause": "media_control", "resume": "media_control", "next": "media_control", "previous": "media_control",
            "lock": "power_control", "sleep": "power_control", "shutdown": "power_control",
            "restart": "power_control", "cancel": "power_control",
            "screenshot": "take_screenshot",
        },
        target_aliases={
            "volume": ["volume", "sound", "audio", "speaker", "speakers"],
            "brightness": ["brightness", "screen brightness", "display brightness"],
            "shutdown": ["shutdown", "shut down", "restart", "reboot"],
        },
        ability="control volume, brightness, music and power",
        default_targets={
            "mute": "volume", "unmute": "volume",
            "pause": "media", "resume": "media", "next": "media", "previous": "media",
            "lock": "computer", "sleep": "computer", "shutdown": "computer", "restart": "computer",
            "screenshot": "screen",
        },
        operation_permissions={"shutdown": PermissionLevel.HIGH, "restart": PermissionLevel.HIGH},
        target_description=(
            "for set/increase/decrease: 'volume' or 'brightness'; set needs parameters.level (0-100); "
            "include parameters.amount only if the user gives a number; "
            "for pause/resume/next/previous: the media; for cancel: 'shutdown' or 'restart'; other operations need no target"
        ),
    )
    timeout_seconds = 15.0

    def health_check(self) -> ToolHealth:
        system = platform.system().lower()
        return ToolHealth(available=system in ("windows", "darwin"), reason=f"System OS: {system}", dependencies=["pycaw (Windows audio)"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        canonical, score = super().match_target(requested, operation)
        if canonical:
            return canonical, score
        # Operations like "mute" or "lock" act on one fixed thing whatever it is called.
        default = self.manifest.default_targets.get(operation or "")
        return (default, 0.8) if default else (None, 0.0)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        operation = args.get("operation")
        if operation not in self.manifest.operations:
            return False, f"Unsupported system operation '{operation}'."
        if operation in ("set", "increase", "decrease") and args.get("target") not in ("volume", "brightness"):
            return False, "I can set or adjust the volume or the screen brightness."
        if operation == "set" and self._percent(args.get("level")) is None:
            return False, "Tell me what level to set it to, from 0 to 100."
        return True, None

    def describe_action(self, args: Dict[str, Any]) -> str:
        operation = args.get("operation")
        if operation == "shutdown":
            return f"shut down the computer in {_POWER_DELAY_SECONDS} seconds"
        if operation == "restart":
            return f"restart the computer in {_POWER_DELAY_SECONDS} seconds"
        return super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation = args["operation"]
        if dry_run:
            return {"dry_run": True, "action": operation, "target": args.get("target")}
        if operation in ("set", "increase", "decrease"):
            return await self._level(operation, args)
        if operation in ("mute", "unmute"):
            return self._mute(operation == "mute")
        if operation in _MEDIA_KEYS:
            return self._media(operation)
        if operation == "screenshot":
            return await self._screenshot()
        return self._power(operation)

    # ----------------------------------------------------------- volume/brightness

    async def _level(self, operation: str, args: Dict[str, Any]) -> Dict[str, Any]:
        target = args["target"]
        read, write = (self._get_volume, self._set_volume) if target == "volume" else (self._get_brightness, self._set_brightness)
        current = await asyncio.to_thread(read)
        if operation == "set":
            wanted = self._percent(args.get("level"))
        else:
            if current is None:
                return self._fail(f"I couldn't read the current {target}")
            step = self._percent(args.get("amount") or args.get("level")) or 10
            wanted = current + step if operation == "increase" else current - step
        wanted = max(0, min(100, wanted))
        await asyncio.to_thread(write, wanted)
        actual = await asyncio.to_thread(read)
        verified = actual is not None and abs(actual - wanted) <= 2
        return {
            "action": operation,
            "target": target,
            "level": actual,
            "success": verified,
            "verified": verified,
            "summary": f"{target.capitalize()} is now at {actual}%." if verified else None,
            "error": None if verified else f"the {target} didn't change (it may not be adjustable on this display)",
        }

    @staticmethod
    def _percent(value: Any) -> Optional[int]:
        match = re.search(r"\d+(?:\.\d+)?", str(value if value is not None else ""))
        if not match:
            return None
        number = float(match.group())
        number = number * 100 if 0 < number <= 1 and "." in match.group() else number
        return int(round(number)) if 0 <= number <= 100 else None

    @staticmethod
    def _endpoint():
        import comtypes
        from pycaw.pycaw import AudioUtilities
        try:
            comtypes.CoInitialize()
        except OSError:
            pass  # already initialized on this thread
        return AudioUtilities.GetSpeakers().EndpointVolume

    def _get_volume(self) -> Optional[int]:
        if platform.system() == "Darwin":
            out = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"], capture_output=True, text=True)
            return int(out.stdout.strip()) if out.stdout.strip().isdigit() else None
        return int(round(self._endpoint().GetMasterVolumeLevelScalar() * 100))

    def _set_volume(self, level: int) -> None:
        if platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {int(level)}"], check=False)
            return
        endpoint = self._endpoint()
        if level > 0:
            endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(level / 100.0, None)

    def _get_brightness(self) -> Optional[int]:
        if platform.system() != "Windows":
            return None
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW,
        )
        value = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
        return int(value) if value.isdigit() else None

    def _set_brightness(self, level: int) -> None:
        if platform.system() != "Windows":
            return
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
             f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Brightness=[byte]{int(level)}; Timeout=[uint32]0}}"],
            capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW,
        )

    def _mute(self, mute: bool) -> Dict[str, Any]:
        if platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume {'with' if mute else 'without'} output muted"], check=False)
            state = mute
        else:
            endpoint = self._endpoint()
            endpoint.SetMute(1 if mute else 0, None)
            state = bool(endpoint.GetMute())
        verified = state == mute
        return {
            "action": "mute" if mute else "unmute",
            "target": "volume",
            "success": verified,
            "verified": verified,
            "summary": ("Muted." if mute else "Sound is back on.") if verified else None,
            "error": None if verified else "the mute state didn't change",
        }

    # -------------------------------------------------------------- media/power

    def _media(self, operation: str) -> Dict[str, Any]:
        if platform.system() != "Windows":
            return self._fail("media keys are only supported on Windows for now")
        key = _MEDIA_KEYS[operation]
        user32 = ctypes.windll.user32
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, 2, 0)  # KEYEVENTF_KEYUP
        # A media key press can't be read back; report exactly what was done.
        label = {"pause": "play/pause", "resume": "play/pause", "next": "next track", "previous": "previous track"}[operation]
        return {"action": operation, "target": "media", "success": True, "verified": True,
                "summary": f"Sent {label} to your media player.", "error": None}

    def _power(self, operation: str) -> Dict[str, Any]:
        system = platform.system()
        if operation == "lock":
            if system == "Windows":
                ok = bool(ctypes.windll.user32.LockWorkStation())
            else:
                ok = subprocess.run(["pmset", "displaysleepnow"]).returncode == 0
            return self._done(ok, "lock", "Locked your computer.", "the lock request was refused")

        if system == "Windows":
            commands = {
                "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                "shutdown": ["shutdown", "/s", "/t", str(_POWER_DELAY_SECONDS)],
                "restart": ["shutdown", "/r", "/t", str(_POWER_DELAY_SECONDS)],
                "cancel": ["shutdown", "/a"],
            }
        else:
            commands = {"sleep": ["pmset", "sleepnow"]}
        command = commands.get(operation)
        if command is None:
            return self._fail(f"{operation} isn't supported on this system yet")
        ok = subprocess.run(command, capture_output=True, creationflags=_NO_WINDOW).returncode == 0
        summaries = {
            "sleep": "Putting the computer to sleep.",
            "shutdown": f"Shutting down in {_POWER_DELAY_SECONDS} seconds. Say 'cancel the shutdown' to stop it.",
            "restart": f"Restarting in {_POWER_DELAY_SECONDS} seconds. Say 'cancel the restart' to stop it.",
            "cancel": "Cancelled the scheduled shutdown.",
        }
        failure = "there was no shutdown scheduled" if operation == "cancel" else f"Windows refused the {operation} request"
        return self._done(ok, operation, summaries[operation], failure)

    async def _screenshot(self) -> Dict[str, Any]:
        folder = Path.home() / "Pictures" / "HARIKA Screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"screenshot-{datetime.now():%Y%m%d-%H%M%S}.png"
        if platform.system() == "Darwin":
            await asyncio.to_thread(subprocess.run, ["screencapture", "-x", str(path)])
        else:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen; "
                "$img=New-Object System.Drawing.Bitmap $b.Width,$b.Height; "
                "$g=[System.Drawing.Graphics]::FromImage($img); "
                "$g.CopyFromScreen($b.Left,$b.Top,0,0,$img.Size); "
                "$img.Save($env:HARIKA_SHOT,[System.Drawing.Imaging.ImageFormat]::Png)"
            )
            # The output path travels in an environment variable, never inside the script text.
            env = {**os.environ, "HARIKA_SHOT": str(path)}
            await asyncio.to_thread(
                subprocess.run,
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=15, env=env, creationflags=_NO_WINDOW,
            )
        ok = path.exists() and path.stat().st_size > 0
        result = self._done(ok, "screenshot", f"Saved a screenshot to {path}.", "the screenshot couldn't be saved")
        result["path"] = str(path)
        return result

    @staticmethod
    def _done(ok: bool, action: str, summary: str, failure: str) -> Dict[str, Any]:
        return {"action": action, "success": ok, "verified": ok,
                "summary": summary if ok else None, "error": None if ok else failure}

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


system_control_tool = SystemControlTool()
tool_registry.register_tool(system_control_tool)
