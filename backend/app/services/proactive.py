"""Heads-ups: HARIKA speaks up on its own, but only about things the user turned on.

- a meeting on their Google Calendar is about to start
- someone they told HARIKA about has a birthday today
- the battery is running low

Each heads-up is shown in HARIKA's windows, sent as a notification, and spoken when
the user talks to HARIKA by voice. Each one happens once (per event, per day, per
discharge), and every kind has its own switch in Settings > General.
"""
import asyncio
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.paths import data_path

logger = logging.getLogger("harika.proactive")

DEFAULTS: Dict[str, Any] = {
    "meetings": True,          # a heads-up before calendar events
    "meeting_minutes": 10,     # how long before
    "birthdays": True,         # on the morning of a birthday
    "battery": True,           # when the battery runs low on battery power
    "battery_percent": 15,
}
_BIRTHDAY_HOUR = 9
_CALENDAR_REFRESH = 300  # seconds between calendar reads


class ProactiveSettings:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("settings", "proactive.json")
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(DEFAULTS)
            try:
                if self.path.exists():
                    stored = json.loads(self.path.read_text(encoding="utf-8"))
                    data.update({k: v for k, v in stored.items() if k in DEFAULTS})
            except (OSError, json.JSONDecodeError):
                logger.warning("[Proactive] Settings unreadable; using defaults.")
            return data

    def update(self, **changes: Any) -> Dict[str, Any]:
        changes = {k: v for k, v in changes.items() if k in DEFAULTS and v is not None}
        if "meeting_minutes" in changes:
            changes["meeting_minutes"] = int(min(60, max(1, int(changes["meeting_minutes"]))))
        if "battery_percent" in changes:
            changes["battery_percent"] = int(min(50, max(5, int(changes["battery_percent"]))))
        data = {**self.load(), **changes}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


proactive_settings = ProactiveSettings()


class HeadsUps:
    """Decides what to say; delivery is separate so the decisions can be tested on their own."""

    def __init__(self, settings: ProactiveSettings = proactive_settings, state_path: Optional[Path] = None):
        self.settings = settings
        self.state_path = state_path or data_path("settings", "proactive_state.json")
        self._events: List[Any] = []
        self._events_read = 0.0
        self._battery_warned = False

    # ------------------------------------------------------------- memory of what was said

    def _state(self) -> Dict[str, Any]:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _remember(self, **changes: Any) -> None:
        state = {**self._state(), **changes}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # ------------------------------------------------------------- the checks

    async def check(self, now: datetime) -> List[Dict[str, str]]:
        settings = self.settings.load()
        found: List[Dict[str, str]] = []
        if settings["meetings"]:
            found += await self.meetings(now, settings["meeting_minutes"])
        if settings["birthdays"]:
            found += self.birthdays(now)
        if settings["battery"]:
            found += self.battery(settings["battery_percent"])
        return found

    async def meetings(self, now: datetime, minutes: int) -> List[Dict[str, str]]:
        from app.integrations.google.account import google_account
        if not google_account.status()["calendar"]:
            return []
        if time.time() - self._events_read > _CALENDAR_REFRESH:
            from app.integrations.google.calendar import google_calendar
            try:
                self._events = await google_calendar.events(now, now + timedelta(hours=3), limit=20)
            except Exception as exc:
                logger.info(f"[Proactive] Calendar unavailable: {exc}")
                self._events = []
            self._events_read = time.time()
        state = self._state()
        told = set(state.get("meetings_told", []))
        out = []
        for event in self._events:
            key = f"{event.id}@{event.start.isoformat()}"  # a moved event gets a fresh heads-up
            lead = (event.start - now).total_seconds() / 60
            if event.all_day or key in told or not 0 <= lead <= minutes:
                continue
            told.add(key)
            when = "now" if lead < 1 else f"in {round(lead)} minute{'s' if round(lead) != 1 else ''}"
            where = f" at {event.location}" if event.location else ""
            out.append({"kind": "meeting", "tone": "warm", "text": f"Heads up: {event.title} starts {when}{where}."})
        if out:
            self._remember(meetings_told=sorted(told)[-50:])
        return out

    def birthdays(self, now: datetime) -> List[Dict[str, str]]:
        if now.hour < _BIRTHDAY_HOUR or self._state().get("birthdays_told") == now.date().isoformat():
            return []
        from app.tools.productivity.people_tool import people_store
        today = [person for person, when, _ in people_store.birthdays(now.date(), within_days=0) if when == now.date()]
        self._remember(birthdays_told=now.date().isoformat())
        out = []
        for person in today:
            suggestion = " Want me to send a message?" if person.get("phone") else ""
            out.append({"kind": "birthday", "tone": "excited", "text": f"It's {person['name']}'s birthday today.{suggestion}"})
        return out

    def battery(self, threshold: int) -> List[Dict[str, str]]:
        from app.core.battery import battery_status
        status = battery_status()
        if status is None:
            return []
        if status.charging or status.percent > threshold + 5:
            self._battery_warned = False  # plugged in or recovered: warn again next time it runs low
            return []
        if status.percent > threshold or self._battery_warned:
            return []
        self._battery_warned = True
        left = f", about {_duration(status.minutes_left)} left" if status.minutes_left else ""
        return [{"kind": "battery", "tone": "calm", "text": f"Your battery is at {status.percent}%{left}. Plug in soon."}]


def _duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    parts = ([f"{hours} hour{'s' if hours != 1 else ''}"] if hours else []) +             ([f"{mins} minute{'s' if mins != 1 else ''}"] if mins or not hours else [])
    return " ".join(parts)


heads_ups = HeadsUps()


def _speak_if_listening(text: str, tone: str = "warm") -> None:
    """Speak heads-ups to people who use HARIKA by voice; never when replies are muted."""
    from app.voice.engine import voice_engine
    voice = voice_engine.settings.load()
    if voice_engine.can_speak() and voice["speak_replies"] != "never" and (voice["wake_word"] or voice["speak_replies"] == "always"):
        voice_engine.speak(text, tone=tone)


async def run_proactive_loop(interval_seconds: float = 30.0) -> None:
    from app.core.live_events import live_events
    from app.tools.system.reminders import show_os_notification

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            for item in await heads_ups.check(datetime.now()):
                live_events.publish("heads_up", kind=item["kind"], text=item["text"], tone=item.get("tone", "warm"))
                await asyncio.to_thread(show_os_notification, "HARIKA", item["text"])
                await asyncio.to_thread(_speak_if_listening, item["text"], item.get("tone", "warm"))
                logger.info(f"[Proactive] {item['kind']}: {item['text']}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[Proactive] Check failed: {exc}")
