"""See and act in the app the user was just using (Windows UI Automation).

Three pieces:
- ForegroundTracker remembers the last window the user worked in that isn't
  HARIKA, so "this chat" still means that app after HARIKA takes focus.
- read_window() collects the visible text of a window through the same
  accessibility interface screen readers use (no screenshots).
- type_into_window() focuses that window's message box and types text with
  Unicode key events (the clipboard is never touched), optionally pressing
  Enter, then checks that the text appeared.
"""
import ctypes
import logging
import platform
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("harika.tools.screen")

IS_WINDOWS = platform.system() == "Windows"
_OWN_PROCESSES = {"harika.exe", "harika-backend.exe"}
_TEXT_TYPES = {"TextControl", "ListItemControl", "HyperlinkControl", "DataItemControl"}
_EDIT_TYPES = {"EditControl", "DocumentControl"}


@dataclass
class WindowInfo:
    hwnd: int
    pid: int
    title: str
    process: str
    seen_at: float = field(default_factory=time.time)

    @property
    def app_name(self) -> str:
        """Friendly app name: the title's last segment ("Chats - WhatsApp" -> "WhatsApp")."""
        for sep in (" - ", " — ", " | "):
            if sep in self.title:
                return self.title.rsplit(sep, 1)[-1].strip() or self.process
        return self.title or self.process.removesuffix(".exe").title()

    @property
    def contact(self) -> str:
        """Who the chat is with, when the title names them ("Ananya - WhatsApp" -> "Ananya")."""
        for sep in (" - ", " — ", " | "):
            if sep in self.title:
                first = self.title.split(sep, 1)[0].strip()
                # Unread counters like "(3) Instagram" aren't names.
                return "" if not first or first.startswith("(") or first == self.app_name else first
        return ""


class ScreenBusy(RuntimeError):
    """The window couldn't be read right now (it kept changing)."""


@dataclass
class WindowText:
    window: WindowInfo
    lines: List[str]
    has_input: bool


# ----------------------------------------------------------------- Win32 bits

if IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.IsWindow.argtypes = [wintypes.HWND]


def _window_info(hwnd: int) -> Optional[WindowInfo]:
    if not hwnd:
        return None
    length = _user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = ""
    handle = _kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if handle:
        try:
            size = wintypes.DWORD(260)
            path = ctypes.create_unicode_buffer(260)
            if _kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
                process = path.value.rsplit("\\", 1)[-1].lower()
        finally:
            _kernel32.CloseHandle(handle)
    return WindowInfo(hwnd=int(hwnd), pid=pid.value, title=buffer.value, process=process)


def window_exists(info: WindowInfo) -> bool:
    if not IS_WINDOWS or not _user32.IsWindow(info.hwnd):
        return False
    current = _window_info(info.hwnd)
    return current is not None and current.pid == info.pid


def is_own_window(info: WindowInfo) -> bool:
    return info.process in _OWN_PROCESSES or info.title.strip() == "HARIKA" or info.title.startswith("HARIKA ")


class ForegroundTracker:
    """Polls the foreground window and keeps the last one that isn't HARIKA."""

    def __init__(self, interval: float = 0.4):
        self.interval = interval
        self.last_external: Optional[WindowInfo] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if not IS_WINDOWS or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="harika-foreground", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                info = _window_info(_user32.GetForegroundWindow())
                if info and info.title and not is_own_window(info):
                    self.last_external = info
            except Exception as exc:  # never let tracking take the backend down
                logger.debug(f"[Screen] foreground poll failed: {exc}")
            self._stop.wait(self.interval)

    def current_target(self) -> Optional[WindowInfo]:
        """The app the user was working in, if it's still open."""
        if not IS_WINDOWS:
            return None
        info = _window_info(_user32.GetForegroundWindow())
        if info and info.title and not is_own_window(info):
            return info
        if self.last_external and window_exists(self.last_external):
            return self.last_external
        return None


foreground_tracker = ForegroundTracker()


# ----------------------------------------------------------------- reading

def read_window(info: WindowInfo, max_seconds: float = 3.0, max_nodes: int = 6000, max_lines: int = 80) -> WindowText:
    """Visible text of a window, top to bottom (the newest chat messages are last)."""
    import uiautomation as auto

    with auto.UIAutomationInitializerInThread():
        found, has_input = [], False
        for attempt in range(3):
            try:
                root = auto.ControlFromHandle(info.hwnd)
                if root is None:
                    return WindowText(info, [], False)
                found, has_input = _collect(root, root.BoundingRectangle, max_seconds, max_nodes)
                if len(found) >= 3:
                    break
                # Chromium-based apps build their accessibility tree on first request.
            except Exception as exc:
                # UI Automation briefly errors while an app redraws (e.g. a page reload).
                logger.debug(f"[Screen] read attempt {attempt + 1} failed: {exc}")
                if attempt == 2:
                    raise ScreenBusy(f"{info.app_name} was busy updating, so I couldn't read it") from exc
            time.sleep(0.5)

    found.sort(key=lambda item: (item[0], item[1]))
    lines: List[str] = []
    for _, _, text in found:
        if not lines or lines[-1] != text:
            lines.append(text)
    return WindowText(info, lines[-max_lines:], has_input)


def _collect(root, window_rect, max_seconds: float, max_nodes: int):
    import uiautomation as auto

    found = []
    has_input = False
    deadline = time.monotonic() + max_seconds
    for count, (control, _depth) in enumerate(auto.WalkControl(root, maxDepth=80)):
        if count > max_nodes or time.monotonic() > deadline:
            break
        try:
            kind = control.ControlTypeName
            if kind in _EDIT_TYPES and control.IsKeyboardFocusable:
                has_input = True
                continue
            if kind not in _TEXT_TYPES or control.IsOffscreen:
                continue
            text = " ".join((control.Name or "").split())
            rect = control.BoundingRectangle
        except Exception:
            continue
        if not text or rect.width() <= 0 or rect.top < window_rect.top or rect.bottom > window_rect.bottom + 2:
            continue
        found.append((rect.top, rect.left, text[:500]))
    return found, has_input


# ----------------------------------------------------------------- typing

def _find_input(root, max_seconds: float = 3.0):
    """A chat app's message box: the bottom-most focusable text field.

    Real edit fields win over documents, and anything taller than half the
    window (a whole web page is a "document") is a container, not a box.
    """
    import uiautomation as auto

    window = root.BoundingRectangle
    best, best_key = None, None
    deadline = time.monotonic() + max_seconds
    for control, _depth in auto.WalkControl(root, maxDepth=80):
        if time.monotonic() > deadline:
            break
        try:
            kind = control.ControlTypeName
            if kind not in _EDIT_TYPES or not control.IsKeyboardFocusable or control.IsOffscreen:
                continue
            rect = control.BoundingRectangle
            if rect.height() <= 0 or rect.height() > window.height() * 0.5:
                continue
            key = (kind == "EditControl", rect.bottom)
            if best_key is None or key > best_key:
                best, best_key = control, key
        except Exception:
            continue
    return best


def _send_unicode(text: str) -> None:
    """Type text with KEYEVENTF_UNICODE events: any language, no clipboard."""
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_byte * 32)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    events = []
    data = text.encode("utf-16-le")  # UTF-16 code units, so emoji/surrogates type correctly
    for i in range(0, len(data), 2):
        code = int.from_bytes(data[i:i + 2], "little")
        for flags in (0x0004, 0x0004 | 0x0002):  # KEYEVENTF_UNICODE, then key-up
            item = INPUT(type=1)
            item.ki = KEYBDINPUT(0, code, flags, 0, None)
            events.append(item)
    array = (INPUT * len(events))(*events)
    _user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def type_into_window(info: WindowInfo, text: str, press_enter: bool) -> Optional[str]:
    """Type into the window's message box; returns an error message, or None on success."""
    import uiautomation as auto

    if not window_exists(info):
        return f"{info.app_name} is no longer open"
    single_line = " ".join(text.split())
    with auto.UIAutomationInitializerInThread():
        root = auto.ControlFromHandle(info.hwnd)
        if root is None:
            return f"I couldn't reach {info.app_name}'s window"
        try:
            root.SetActive()  # brings the window forward (handles Windows' focus-stealing rules)
        except Exception:
            pass
        time.sleep(0.3)
        box = _find_input(root)
        if box is None:
            return f"I couldn't find a message box in {info.app_name}"
        try:
            box.SetFocus()
        except Exception:
            box.Click(simulateMove=False)
        time.sleep(0.2)
        foreground = _window_info(_user32.GetForegroundWindow())
        if foreground is None or foreground.pid != info.pid:
            # Never type into whatever else happens to be in front.
            return f"{info.app_name} didn't come to the front, so I didn't type anything"
        _send_unicode(single_line)
        if press_enter:
            time.sleep(0.15)
            auto.SendKey(auto.Keys.VK_RETURN)
    return None


def text_visible(info: WindowInfo, text: str) -> bool:
    """Whether (the start of) a message now shows in the window."""
    probe = " ".join(text.split())[:24].lower()
    try:
        lines = read_window(info, max_seconds=2.0).lines
    except Exception:
        return False
    return any(probe in line.lower() for line in lines[-25:])


def find_app_window(process_hint: str) -> Optional[WindowInfo]:
    """A visible top-level window whose process name contains `process_hint` (e.g. "whatsapp")."""
    if not IS_WINDOWS:
        return None
    import uiautomation as auto

    with auto.UIAutomationInitializerInThread():
        for window in auto.GetRootControl().GetChildren():
            try:
                info = _window_info(window.NativeWindowHandle)
            except Exception:
                continue
            if info and process_hint in info.process and info.title and not window.IsOffscreen:
                return info
    return None


def _box_text(box) -> str:
    for read in (lambda: box.GetValuePattern().Value, lambda: box.GetTextPattern().DocumentRange.GetText(-1)):
        try:
            value = read()
            if value:
                return str(value)
        except Exception:
            continue
    return ""


def send_prefilled(info: WindowInfo, text: str) -> Optional[str]:
    """Press Enter in the message box only if it holds exactly `text` (put there by the app itself).

    Apps such as WhatsApp prefill a message only in the chat a link opened, so a
    matching box proves the right chat is showing; anything else sends nothing.
    """
    import uiautomation as auto

    if not window_exists(info):
        return f"{info.app_name} is no longer open"
    wanted = " ".join(text.split())
    with auto.UIAutomationInitializerInThread():
        root = auto.ControlFromHandle(info.hwnd)
        if root is None:
            return f"I couldn't reach {info.app_name}'s window"
        try:
            root.SetActive()
        except Exception:
            pass
        time.sleep(0.3)
        box = _find_input(root)
        if box is None:
            return f"I couldn't find the message box in {info.app_name}"
        if " ".join(_box_text(box).split()) != wanted:
            return f"{info.app_name} didn't open the chat with the message ready, so I didn't send anything"
        try:
            box.SetFocus()
        except Exception:
            box.Click(simulateMove=False)
        time.sleep(0.2)
        foreground = _window_info(_user32.GetForegroundWindow())
        if foreground is None or foreground.pid != info.pid:
            return f"{info.app_name} didn't come to the front, so I didn't send anything"
        auto.SendKey(auto.Keys.VK_RETURN)
    return None
