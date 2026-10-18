"""Watching an app: "tell me when Claude finishes", "let me know when Chrome says download complete".

HARIKA reads the app's visible text every few seconds (Windows OCR if the app hides
its text) and compares it on this computer; nothing is sent anywhere while watching.
"Finished" means the content was changing and has now stayed still for a while; a
named piece of text means waiting until that text appears. When it happens, the user
gets a heads-up (in HARIKA, a notification, and spoken if they use voice).
"""
import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

logger = logging.getLogger("harika.tools.watch")

POLL_SECONDS = 4.0
STILL_SECONDS = 25.0          # no change for this long after activity = finished
IDLE_FROM_START_SECONDS = 90.0  # never changed at all: probably already finished
MAX_WATCH_SECONDS = 3 * 3600
_HERE = {"", "it", "this", "that", "the app", "this app", "this window", "screen"}


@dataclass
class Watch:
    id: str
    app: str
    window: Any
    wanted_text: str = ""
    started: float = field(default_factory=time.time)
    task: Optional[asyncio.Task] = None


def snapshot_of(lines: List[str]) -> str:
    return hashlib.sha1("\n".join(lines[-120:]).encode("utf-8", "ignore")).hexdigest()


class WatchTool(BaseTool):
    manifest = ToolManifest(
        name="watch",
        display_name="Watch",
        description="Keeps an eye on an open app and tells you when it finishes or when some text appears.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows"],
        capabilities=["watch_app", "stop_watch"],
        operations={"watch": "watch_app", "stop_watching": "stop_watch"},
        free_text_operations=["watch", "stop_watching"],
        default_targets={"watch": "this", "stop_watching": "all"},
        ability="watch an app and tell you when it's done",
        target_description=(
            "for watch: the open app to watch ('claude', 'chrome'; 'this' for the app the user was just using), with "
            "parameters.text only if the user named words to wait for (e.g. 'Download complete'); "
            "for stop_watching: the app, or 'all'"
        ),
    )
    timeout_seconds = 30.0

    def __init__(self, reader: Optional[Callable[[Any], List[str]]] = None, notify: Optional[Callable[[str, str], None]] = None):
        self._reader = reader
        self._notify = notify
        self.watches: Dict[str, Watch] = {}

    def health_check(self) -> ToolHealth:
        from app.tools.system import screen_reader
        return ToolHealth(available=screen_reader.IS_WINDOWS, reason="Windows UI Automation and OCR", dependencies=["uiautomation"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        return ((requested or "").strip() or self.manifest.default_targets.get(operation or "", "")), 0.7

    def describe_action(self, args: Dict[str, Any]) -> str:
        if args.get("operation") == "stop_watching":
            return "stop watching"
        return f"watch {args.get('target') or 'the app'}"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        target = str(args.get("target") or "").strip()
        if args.get("operation") == "stop_watching":
            return self._stop(target)
        window = await asyncio.to_thread(self._find, target)
        if window is None:
            return self._fail(f"I don't see {target or 'that app'} open. Open it and ask me again")
        if dry_run:
            return {"dry_run": True, "action": "watch_app", "window": window.title}
        first = await asyncio.to_thread(self._read, window)
        if not first:
            return self._fail(f"I can't read {window.app_name} right now. If it's minimized, bring it back and ask again")
        wanted = str(args.get("text") or "").strip().strip("\"“”")
        watch = Watch(uuid.uuid4().hex[:8], window.app_name, window, wanted)
        watch.task = asyncio.create_task(self._watch(watch, snapshot_of(first)))
        self.watches[watch.id] = watch
        what = f"says “{wanted}”" if wanted else "finishes"
        return {"action": "watch_app", "app": window.app_name, "success": True, "verified": True, "tone": "warm",
                "summary": f"Okay, I'll keep an eye on {window.app_name} and tell you when it {what}.", "error": None}

    # ------------------------------------------------------------- watching

    async def _watch(self, watch: Watch, last: str) -> None:
        changed_at: Optional[float] = None
        still_since = time.time()
        try:
            while time.time() - watch.started < MAX_WATCH_SECONDS:
                await asyncio.sleep(POLL_SECONDS)
                from app.tools.system import screen_reader
                if not await asyncio.to_thread(screen_reader.window_exists, watch.window):
                    return self._announce(watch, f"{watch.app} was closed, so I stopped watching it.", "calm")
                lines = await asyncio.to_thread(self._read, watch.window)
                if not lines:
                    continue  # unreadable for a moment (minimized, redrawing)
                if watch.wanted_text:
                    if watch.wanted_text.lower() in "\n".join(lines).lower():
                        return self._announce(watch, f"{watch.app} now says “{watch.wanted_text}”.", "cheerful")
                    continue
                now = time.time()
                current = snapshot_of(lines)
                if current != last:
                    last, changed_at, still_since = current, now, now
                elif changed_at and now - still_since >= STILL_SECONDS:
                    return self._announce(watch, f"{watch.app} looks finished. It's stopped changing.", "cheerful")
                elif changed_at is None and now - watch.started >= IDLE_FROM_START_SECONDS:
                    return self._announce(watch, f"{watch.app} hasn't changed since you asked, so it may already be done.", "calm")
            self._announce(watch, f"I watched {watch.app} for three hours and nothing finished, so I've stopped.", "calm")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[Watch] Watching {watch.app} failed: {exc}")
            self._announce(watch, f"I lost track of {watch.app}, sorry. Ask me again if you still need me to watch it.", "apologetic")
        finally:
            self.watches.pop(watch.id, None)

    def _announce(self, watch: Watch, text: str, tone: str) -> None:
        logger.info(f"[Watch] {text}")
        if self._notify:
            self._notify(text, tone)
            return
        from app.core.live_events import live_events
        from app.services.proactive import _speak_if_listening
        from app.tools.system.reminders import show_os_notification
        import threading
        live_events.publish("heads_up", kind="watch", text=text, tone=tone)
        threading.Thread(target=lambda: (show_os_notification("HARIKA", text), _speak_if_listening(text, tone)),
                         name="harika-watch-notify", daemon=True).start()

    # ------------------------------------------------------------- helpers

    def _stop(self, target: str) -> Dict[str, Any]:
        words = target.lower()
        chosen = [w for w in self.watches.values() if words in ("all", "", "everything") or words in w.app.lower()]
        if not chosen:
            return self._fail("I'm not watching anything right now" if not self.watches else f"I'm not watching {target}")
        for watch in chosen:
            if watch.task:
                watch.task.cancel()
            self.watches.pop(watch.id, None)
        names = ", ".join(sorted({w.app for w in chosen}))
        return {"action": "stop_watch", "success": True, "verified": True, "summary": f"Okay, I stopped watching {names}.", "error": None}

    @staticmethod
    def _find(target: str):
        from app.tools.system import screen_reader
        if target.lower() in _HERE:
            return screen_reader.foreground_tracker.current_target()
        from app.tools.system.device import find_window
        return find_window(target)

    def _read(self, window) -> List[str]:
        if self._reader:
            return self._reader(window)
        from app.tools.system import screen_reader
        try:
            lines = screen_reader.read_window(window, max_seconds=2.0).lines
        except Exception:
            lines = []
        if lines:
            return lines
        from app.vision import screen  # the app hides its text: read the picture instead
        pixels = screen.capture_window(window.hwnd)
        return screen.ocr(screen.png(pixels)) if pixels is not None else []

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


watch_tool = WatchTool()
tool_registry.register_tool(watch_tool)
