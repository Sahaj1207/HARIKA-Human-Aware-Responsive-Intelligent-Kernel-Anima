import asyncio
import json
import logging
import os
import platform
import re
import subprocess
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest
from app.core.paths import data_path

logger = logging.getLogger("harika.tools.reminders")

_DATA_FILE = data_path("reminders", "reminders.json")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ReminderStore:
    """Reminders persisted to disk so they survive restarts."""

    def __init__(self, path: Path = _DATA_FILE):
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self.path.exists():
                return []
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("[Reminders] Store unreadable; starting empty.")
                return []

    def save(self, items: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def add(self, text: str, due: datetime) -> Dict[str, Any]:
        item = {"id": uuid.uuid4().hex[:8], "text": text, "due": due.isoformat(timespec="seconds"), "fired": False}
        self.save(self.load() + [item])
        return item

    def pending(self) -> List[Dict[str, Any]]:
        return sorted((r for r in self.load() if not r["fired"]), key=lambda r: r["due"])

    def mark_fired(self, reminder_id: str) -> None:
        items = self.load()
        for item in items:
            if item["id"] == reminder_id:
                item["fired"] = True
        self.save(items)

    def cancel(self, reminder_id: str) -> None:
        self.save([r for r in self.load() if r["id"] != reminder_id])


class MomentStore:
    """Reminders tied to a moment instead of a time.

    "person": when the user next talks to or about someone ("when I talk to Priya");
    "back": when the user is back at the computer after being away (or opens HARIKA again).
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("reminders", "moments.json")
        self._lock = threading.Lock()

    def load(self) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            except (OSError, json.JSONDecodeError):
                return []

    def _save(self, items: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, text: str, kind: str, person: str = "", now: Optional[float] = None) -> Dict[str, Any]:
        import time
        item = {"id": uuid.uuid4().hex[:8], "text": text, "kind": kind, "person": person.strip(),
                "created": now if now is not None else time.time()}
        self._save(self.load() + [item])
        return item

    def remove(self, ids: List[str]) -> None:
        self._save([r for r in self.load() if r["id"] not in ids])

    def take_mentions(self, texts: List[str], before: float) -> List[Dict[str, Any]]:
        """Person reminders whose person appears in these texts (made before `before`); removes them."""
        words = " ".join(t for t in texts if t).lower()
        due = [r for r in self.load() if r["kind"] == "person" and r["created"] < before and r["person"]
               and re.search(rf"\b{re.escape(r['person'].lower())}\b", words)]
        self.remove([r["id"] for r in due])
        return due

    def take_back(self, before: float) -> List[Dict[str, Any]]:
        due = [r for r in self.load() if r["kind"] == "back" and r["created"] < before]
        self.remove([r["id"] for r in due])
        return due


moment_store = MomentStore()


def _moment(parameters: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """("person", name) or ("back", "") when the reminder is for a moment rather than a time."""
    person = str(parameters.get("person") or "").strip()
    if person:
        return "person", person
    if str(parameters.get("when") or "").strip().lower() == "back":
        return "back", ""
    return None


def _moment_phrase(kind: str, person: str) -> str:
    return f"when you talk to {person}" if kind == "person" else "when you're back at your computer"


def parse_due(parameters: Dict[str, Any], now: Optional[datetime] = None) -> Optional[datetime]:
    """Due time from structured parameters: in_seconds/in_minutes/in_hours, or at (clock time / ISO)."""
    now = now or datetime.now()
    offset = timedelta()
    for key, unit in (("in_seconds", "seconds"), ("in_minutes", "minutes"), ("in_hours", "hours")):
        value = _number(parameters.get(key))
        if value is not None:
            offset += timedelta(**{unit: value})
    if offset:
        return now + offset

    at = str(parameters.get("at") or "").strip().lower()
    if not at:
        return None
    try:
        due = datetime.fromisoformat(at.replace("z", ""))
        return due if due.tzinfo is None else due.astimezone().replace(tzinfo=None)
    except ValueError:
        pass
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", at)
    if not match:
        return None
    hour, minute, meridiem = int(match.group(1)), int(match.group(2) or 0), (match.group(3) or "").replace(".", "")
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return due if due > now else due + timedelta(days=1)


def _number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match and float(match.group()) > 0 else None


def _spoken_time(due: datetime, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    clock = due.strftime("%I:%M %p").lstrip("0")
    if due.date() == now.date():
        return f"at {clock}"
    if due.date() == (now + timedelta(days=1)).date():
        return f"tomorrow at {clock}"
    return f"on {due:%A %d %B} at {clock}"


class RemindersTool(BaseTool):
    """Creates, lists and cancels reminders and timers."""

    manifest = ToolManifest(
        name="reminders",
        display_name="Reminders",
        description="Sets reminders and timers, lists upcoming ones, and cancels them.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["create_reminder", "list_reminders", "cancel_reminder"],
        operations={"remind": "create_reminder", "list": "list_reminders", "cancel": "cancel_reminder"},
        ability="set reminders and timers",
        free_text_operations=["remind", "cancel"],
        target_aliases={"reminders": ["reminders", "my reminders", "timers", "alarms"]},
        default_targets={"list": "reminders"},
        target_description=(
            "for remind: what to be reminded about, or 'timer' for a plain timer, with the time in parameters, or "
            "instead of a time parameters.person (remind when the user next talks to or about that person) or "
            "parameters.when = 'back' (remind when the user is back at the computer); "
            "for list: 'reminders'; for cancel: words from the reminder"
        ),
    )
    timeout_seconds = 5.0

    def __init__(self, store: Optional[ReminderStore] = None, moments: Optional[MomentStore] = None):
        self.store = store or ReminderStore()
        self.moments = moments or moment_store

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Reminder store ready", dependencies=[])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        if operation in ("remind", "cancel"):
            # The reminder's own words; "timer" must stay "timer", not the list alias "timers".
            text = (requested or "").strip()
            return (text, 0.6) if text else (None, 0.0)
        canonical, score = super().match_target(requested, operation)
        if canonical is None and operation in self.manifest.default_targets:
            return self.manifest.default_targets[operation], 0.8
        return canonical, score

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if args.get("operation") == "remind" and parse_due(args) is None and _moment(args) is None:
            return False, "When should I remind you? For example 'in 10 minutes' or 'at 6 pm'."
        return True, None

    def describe_action(self, args: Dict[str, Any]) -> str:
        operation, text = args.get("operation"), str(args.get("target") or "").strip()
        if operation == "remind":
            moment = _moment(args)
            if moment and parse_due(args) is None:
                return f"remind you to {text} {_moment_phrase(*moment)}"
            due = parse_due(args)
            when = f" {_spoken_time(due)}" if due else ""
            return f"set a timer{when}" if text.lower() == "timer" else f"remind you to {text}{when}"
        if operation == "list":
            return "list your reminders"
        if operation == "cancel":
            return f"cancel the reminder to {text}"
        return super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation = args.get("operation")
        if operation == "remind" and parse_due(args) is None and _moment(args):
            kind, person = _moment(args)
            text = str(args.get("target") or "your reminder").strip()
            if dry_run:
                return {"dry_run": True, "action": "create_reminder", "text": text, "moment": kind}
            item = self.moments.add(text, kind, person)
            return {"action": "create_reminder", "reminder": item, "success": True, "verified": True,
                    "summary": f"I'll remind you to {text} {_moment_phrase(kind, person)}.", "error": None}
        if operation == "remind":
            due = parse_due(args)
            text = str(args.get("target") or "your reminder").strip()
            if dry_run:
                return {"dry_run": True, "action": "create_reminder", "text": text, "due": due.isoformat()}
            item = self.store.add(text, due)
            label = "Timer set" if text.lower() == "timer" else f"I'll remind you to {text}"
            return {"action": "create_reminder", "reminder": item, "success": True, "verified": True,
                    "summary": f"{label} {_spoken_time(due)}.", "error": None}

        pending = self.store.pending()
        moments = self.moments.load()
        if operation == "list":
            if not pending and not moments:
                return {"action": "list_reminders", "success": True, "verified": True,
                        "summary": "You have no upcoming reminders.", "error": None}
            listing = "; ".join(
                [f"{r['text']} {_spoken_time(datetime.fromisoformat(r['due']))}" for r in pending[:5]]
                + [f"{r['text']} {_moment_phrase(r['kind'], r['person'])}" for r in moments[:5]])
            return {"action": "list_reminders", "reminders": pending, "success": True, "verified": True,
                    "summary": f"Upcoming: {listing}.", "error": None}

        words = set(re.findall(r"[a-z0-9]+", str(args.get("target") or "").lower())) - {"reminder", "reminders", "my", "the", "timer"}
        candidates = pending + moments
        matches = [r for r in candidates if words & set(re.findall(r"[a-z0-9]+", r["text"].lower()))] if words else pending[-1:]
        if len(matches) != 1:
            reason = "I couldn't find a matching upcoming reminder" if not matches else f"{len(matches)} reminders match, so tell me which one"
            return {"action": "cancel_reminder", "success": False, "verified": False, "error": reason}
        if not dry_run:
            if "kind" in matches[0]:
                self.moments.remove([matches[0]["id"]])
            else:
                self.store.cancel(matches[0]["id"])
        return {"action": "cancel_reminder", "success": True, "verified": True,
                "summary": f"Cancelled the reminder to {matches[0]['text']}.", "error": None}


async def run_reminder_scheduler(tool: "RemindersTool", interval_seconds: float = 1.0) -> None:
    """Fire due reminders: a live event for open HARIKA windows plus an OS notification."""
    from app.core.live_events import live_events

    while True:
        now = datetime.now()
        for item in tool.store.pending():
            if datetime.fromisoformat(item["due"]) > now:
                break
            tool.store.mark_fired(item["id"])
            text = "Your timer is done." if item["text"].lower() == "timer" else f"Reminder: {item['text']}"
            live_events.publish("reminder", id=item["id"], text=text, due=item["due"])
            await asyncio.to_thread(show_os_notification, "HARIKA", text)
            logger.info(f"[Reminders] Fired {item['id']}.")
        await asyncio.sleep(interval_seconds)


def show_os_notification(title: str, text: str) -> None:
    """Native notification; the text travels as data (env/argv), never inside script source."""
    try:
        if platform.system() == "Windows":
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
                "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                "$n=$t.GetElementsByTagName('text');"
                "$n.Item(0).AppendChild($t.CreateTextNode($env:HARIKA_TITLE)) > $null;"
                "$n.Item(1).AppendChild($t.CreateTextNode($env:HARIKA_TEXT)) > $null;"
                "$app='{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe';"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($t))"
            )
            env = {**os.environ, "HARIKA_TITLE": title, "HARIKA_TEXT": text}
            subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                           env=env, capture_output=True, timeout=15, creationflags=_NO_WINDOW)
        elif platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", "on run argv", "-e",
                            "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run", title, text],
                           capture_output=True, timeout=15)
    except Exception as exc:
        logger.warning(f"[Reminders] OS notification failed: {exc}")


reminders_tool = RemindersTool()
tool_registry.register_tool(reminders_tool)
