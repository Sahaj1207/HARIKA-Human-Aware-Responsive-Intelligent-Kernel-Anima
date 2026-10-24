"""Heads-ups: HARIKA speaks up on its own, but only about things the user turned on.

- a meeting on their Google Calendar is about to start
- someone they told HARIKA about has a birthday today
- the battery is running low
- something the user habitually asks for is usually done about now (Settings > Memory)
- reminders set for "when I'm back" once the user returns to the computer

A meeting with a video link comes with an offer to open it; the offer waits for the
user's yes like any other approval. Quiet hours silence everything but a low battery,
and suggestions (habits) are limited per day.

Each heads-up is shown in HARIKA's windows, sent as a notification, and spoken when
the user talks to HARIKA by voice. Each one happens once (per event, per day, per
discharge), and every kind has its own switch in Settings > General.
"""
import asyncio
import json
import logging
import re
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
    "quiet_hours": True,       # no heads-ups (except low battery) between these times
    "quiet_start": "23:00",
    "quiet_end": "07:00",
    "suggestions_per_day": 3,  # habit suggestions at most this often
}
_AWAY_SECONDS = 600  # no keyboard or mouse for this long counts as being away
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
        for key in ("quiet_start", "quiet_end"):
            if key in changes and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(changes[key])):
                raise ValueError(f"{key} must be HH:MM (24-hour).")
        if "suggestions_per_day" in changes:
            changes["suggestions_per_day"] = int(min(10, max(0, int(changes["suggestions_per_day"]))))
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
        self._started = time.time()
        self._away = False
        self._checked_return = False

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

    async def check(self, now: datetime) -> List[Dict[str, Any]]:
        settings = self.settings.load()
        found: List[Dict[str, Any]] = []
        if settings["battery"]:
            found += self.battery(settings["battery_percent"])
        if quiet(settings, now):
            return found  # the rest waits (meetings and birthdays are simply skipped at night)
        found += self.welcome_back(now)
        if settings["meetings"]:
            found += await self.meetings(now, settings["meeting_minutes"])
        if settings["birthdays"]:
            found += self.birthdays(now)
        found += self.habits(now, settings["suggestions_per_day"])
        return found

    def welcome_back(self, now: datetime) -> List[Dict[str, str]]:
        """Reminders for "when I'm back": after the user was away, or when HARIKA starts again."""
        from app.core.idle import seconds_idle
        from app.tools.system.reminders import moment_store

        idle = seconds_idle()
        first = not self._checked_return
        self._checked_return = True
        if idle is not None and idle >= _AWAY_SECONDS:
            self._away = True
            return []
        if first:
            since = self._started  # anything set before HARIKA started is "while you were away"
        elif self._away:
            since, self._away = time.time(), False  # nothing can be set while away, so all of it is due
        else:
            return []
        due = moment_store.take_back(before=since)
        if not due:
            return []
        items = "; ".join(r["text"] for r in due)
        return [{"kind": "reminder", "tone": "warm", "text": f"Welcome back. You asked me to remind you: {items}."}]

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
            where = f" at {event.location}" if event.location and event.location not in event.meeting_url else ""
            item: Dict[str, Any] = {"kind": "meeting", "tone": "warm", "text": f"Heads up: {event.title} starts {when}{where}."}
            if event.meeting_url:
                item["text"] = f"Heads up: {event.title} starts {when}. Want me to open the meeting?"
                # Open until a little after the start; "yes" opens the link, nothing happens otherwise.
                item["offer"] = {"capability": "open_website", "operation": "open", "target": event.meeting_url,
                                 "question": f"Should I open the {event.title} meeting?",
                                 "ttl": max(120.0, (event.start - now).total_seconds() + 600)}
            out.append(item)
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


    def habits(self, now: datetime, limit: int = 3) -> List[Dict[str, str]]:
        from app.memory.journal import journal
        from app.memory.patterns import habits
        if not journal.settings()["notice_habits"]:
            return []
        today = now.date().isoformat()
        told = {k: v for k, v in self._state().get("habits_told", {}).items() if v == today}
        out = []
        for habit in habits.due(now):
            if habit["id"] in told or len(told) >= limit:
                continue
            told[habit["id"]] = today
            out.append({"kind": "habit", "tone": "warm",
                        "text": f"You usually {habit['label']} around this time. Just say the word if you'd like that now."})
        if out:
            self._remember(habits_told=told)
        return out


def quiet(settings: Dict[str, Any], now: datetime) -> bool:
    """Within quiet hours (which may run past midnight)."""
    if not settings["quiet_hours"]:
        return False
    start, end, current = settings["quiet_start"], settings["quiet_end"], now.strftime("%H:%M")
    return start <= current < end if start <= end else current >= start or current < end


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
                if item.get("offer"):
                    from app.memory.journal import journal
                    from app.router.manager import router_manager
                    router_manager.offer(item["offer"], user_id=journal.owner())
                live_events.publish("heads_up", kind=item["kind"], text=item["text"], tone=item.get("tone", "warm"))
                from app.router.manager import router_manager
                router_manager.note("assistant", item["text"])  # so "okay" or "thanks" after it makes sense
                await asyncio.to_thread(show_os_notification, "HARIKA", item["text"])
                await asyncio.to_thread(_speak_if_listening, item["text"], item.get("tone", "warm"))
                logger.info(f"[Proactive] {item['kind']}: {item['text']}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[Proactive] Check failed: {exc}")
