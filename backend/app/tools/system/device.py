"""Device: battery, Wi-Fi and Bluetooth, dark mode, showing the desktop and switching windows.

Every change uses a fixed OS interface (WinRT radios, the per-user theme registry
values, a key press, a window handle) and is read back to verify it took effect.
Nothing here takes free text into a command line: radio kinds and states are
passed as data in environment variables.
"""
import asyncio
import ctypes
import os
import platform
import re
import subprocess
from typing import Any, Dict, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_IS_WINDOWS = platform.system() == "Windows"
_THEME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_RADIOS = {"wifi": "WiFi", "bluetooth": "Bluetooth"}

# Windows Runtime radio control from PowerShell 5.1. Inputs arrive only through
# $env:HARIKA_RADIO ("WiFi"/"Bluetooth") and $env:HARIKA_STATE ("On"/"Off"/"").
_RADIO_SCRIPT = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$radio = $radios | Where-Object { $_.Kind -eq $env:HARIKA_RADIO } | Select-Object -First 1
if (-not $radio) { Write-Output 'missing'; exit }
if ($env:HARIKA_STATE) {
  Await ($radio.SetStateAsync($env:HARIKA_STATE)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
  Start-Sleep -Milliseconds 800
}
Write-Output $radio.State
"""


def radio(kind: str, state: str = "") -> Optional[str]:
    """Reads (or sets, then reads) a radio: 'On', 'Off', 'Disabled', 'missing', or None if unavailable."""
    if not _IS_WINDOWS:
        return None
    env = {**os.environ, "HARIKA_RADIO": _RADIOS[kind], "HARIKA_STATE": state}
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _RADIO_SCRIPT],
                             env=env, capture_output=True, text=True, timeout=20, creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
    return lines[-1] if lines else None


def dark_mode() -> Optional[bool]:
    if not _IS_WINDOWS:
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _THEME_KEY) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return None


def set_dark_mode(on: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _THEME_KEY, 0, winreg.KEY_SET_VALUE) as key:
        for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0 if on else 1)
    # Tell open windows the theme changed (WM_SETTINGCHANGE "ImmersiveColorSet").
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet", 0x0002, 2000, ctypes.byref(result))


def show_desktop() -> None:
    """Win+D: shows the desktop (pressing it again brings the windows back)."""
    user32 = ctypes.windll.user32
    for key, flags in ((0x5B, 0), (0x44, 0), (0x44, 2), (0x5B, 2)):  # LWin down, D down, D up, LWin up
        user32.keybd_event(key, 0, flags, 0)


def find_window(name: str):
    """An open top-level window for an app the user names ("chrome", "whatsapp", "my notes in notepad")."""
    from app.tools.system import screen_reader
    import uiautomation as auto

    wanted = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in ("the", "my", "app", "window")]
    if not wanted:
        return None
    with auto.UIAutomationInitializerInThread():
        for window in auto.GetRootControl().GetChildren():
            try:
                info = screen_reader._window_info(window.NativeWindowHandle)
            except Exception:
                continue
            if not info or not info.title or screen_reader.is_own_window(info):
                continue
            haystack = f"{info.title} {info.process.removesuffix('.exe')}".lower()
            if all(w in haystack for w in wanted):
                return info
    return None


def bring_forward(info) -> bool:
    import uiautomation as auto
    from app.tools.system import screen_reader

    with auto.UIAutomationInitializerInThread():
        root = auto.ControlFromHandle(info.hwnd)
        if root is None:
            return False
        try:
            if ctypes.windll.user32.IsIconic(info.hwnd):
                ctypes.windll.user32.ShowWindow(info.hwnd, 9)  # SW_RESTORE
            root.SetActive()
        except Exception:
            return False
    front = screen_reader._window_info(ctypes.windll.user32.GetForegroundWindow())
    return front is not None and front.pid == info.pid


class DeviceTool(BaseTool):
    manifest = ToolManifest(
        name="device",
        display_name="Device",
        description="Battery status, Wi-Fi and Bluetooth on/off, dark mode, showing the desktop and switching to an open app.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows"],
        capabilities=["battery_status", "toggle_setting", "show_desktop", "switch_window"],
        operations={"battery": "battery_status", "turn_on": "toggle_setting", "turn_off": "toggle_setting",
                    "show_desktop": "show_desktop", "switch_to": "switch_window"},
        free_text_operations=["switch_to"],
        target_aliases={
            "wifi": ["wifi", "wi-fi", "wi fi", "wireless", "internet"],
            "bluetooth": ["bluetooth", "blue tooth"],
            "dark mode": ["dark mode", "dark theme", "night theme"],
            "light mode": ["light mode", "light theme"],
        },
        default_targets={"battery": "battery", "show_desktop": "desktop"},
        ability="check the battery, turn Wi-Fi, Bluetooth and dark mode on or off, and switch between apps",
        target_description=(
            "for turn_on/turn_off: 'wifi', 'bluetooth', 'dark mode' or 'light mode'; "
            "for switch_to: the open app to bring to the front ('chrome', 'whatsapp')"
        ),
    )
    timeout_seconds = 30.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=_IS_WINDOWS, reason="Windows settings and windows", dependencies=["uiautomation"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        if operation == "switch_to":
            text = (requested or "").strip()
            return (text, 0.7) if text else (None, 0.0)
        canonical, score = super().match_target(requested, operation)
        if canonical is None and operation in self.manifest.default_targets:
            return self.manifest.default_targets[operation], 0.8
        return canonical, score

    def describe_action(self, args: Dict[str, Any]) -> str:
        operation, target = args.get("operation"), str(args.get("target") or "")
        if operation in ("turn_on", "turn_off"):
            return f"turn {target} {'on' if operation == 'turn_on' else 'off'}"
        labels = {"battery": "check the battery", "show_desktop": "show the desktop", "switch_to": f"switch to {target}"}
        return labels.get(operation) or super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation, target = args.get("operation"), str(args.get("target") or "").strip().lower()
        if dry_run:
            return {"dry_run": True, "action": operation, "target": target}
        if operation == "battery":
            return self._battery()
        if operation in ("turn_on", "turn_off"):
            on = operation == "turn_on"
            if target in ("dark mode", "light mode"):
                return await self._theme(on if target == "dark mode" else not on)
            if target in _RADIOS:
                return await self._radio(target, on)
            return self._fail(f"I can turn Wi-Fi, Bluetooth or dark mode on and off, not {target}")
        if operation == "show_desktop":
            await asyncio.to_thread(show_desktop)
            return self._ok("show_desktop", True, "Here's your desktop. Say it again to bring your windows back.")
        if operation == "switch_to":
            return await self._switch(target)
        return self._fail(f"I can't do '{operation}' here")

    def _battery(self) -> Dict[str, Any]:
        from app.core.battery import battery_status
        from app.services.proactive import _duration
        status = battery_status()
        if status is None:
            return self._fail("This computer doesn't report a battery")
        if status.charging:
            summary = f"Battery is at {status.percent}% and charging."
        else:
            left = f", about {_duration(status.minutes_left)} left" if status.minutes_left else ""
            summary = f"Battery is at {status.percent}%{left}."
        return self._ok("battery_status", True, summary)

    async def _theme(self, dark: bool) -> Dict[str, Any]:
        await asyncio.to_thread(set_dark_mode, dark)
        verified = await asyncio.to_thread(dark_mode) == dark
        return self._ok("toggle_setting", verified, f"Switched to {'dark' if dark else 'light'} mode.",
                        "the theme didn't change")

    async def _radio(self, kind: str, on: bool) -> Dict[str, Any]:
        name = "Wi-Fi" if kind == "wifi" else "Bluetooth"
        state = await asyncio.to_thread(radio, kind, "On" if on else "Off")
        if state is None:
            return self._fail(f"I couldn't reach Windows' {name} setting")
        if state == "missing":
            return self._fail(f"This computer doesn't seem to have {name}")
        if state == "Disabled":
            return self._fail(f"{name} is switched off in Windows (or by airplane mode), so I can't turn it {'on' if on else 'off'} from here")
        verified = state == ("On" if on else "Off")
        return self._ok("toggle_setting", verified, f"{name} is {'on' if on else 'off'}.",
                        f"{name} is still {state.lower()}")

    async def _switch(self, name: str) -> Dict[str, Any]:
        window = await asyncio.to_thread(find_window, name)
        if window is None:
            return self._fail(f"{name.capitalize()} doesn't seem to be open. Say “open {name}” to start it")
        front = await asyncio.to_thread(bring_forward, window)
        return self._ok("switch_window", front, f"Switched to {window.app_name}.",
                        f"{window.app_name} didn't come to the front")

    @staticmethod
    def _ok(action: str, verified: bool, summary: str, failure: str = "") -> Dict[str, Any]:
        return {"action": action, "success": verified, "verified": verified,
                "summary": summary if verified else None, "error": None if verified else failure}

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


device_tool = DeviceTool()
tool_registry.register_tool(device_tool)
