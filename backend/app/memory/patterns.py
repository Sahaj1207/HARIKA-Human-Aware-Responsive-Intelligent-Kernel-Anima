"""Habits: things the user asks HARIKA to do at about the same time, again and again.

Found from the journal's successful actions, never from guesses: the same action
(capability, operation and target) at a similar time of day on at least
_DAILY_DAYS different days, or on the same weekday in at least _WEEKLY_WEEKS
different weeks. A habit only ever becomes a gentle heads-up a few minutes before
its usual time; HARIKA never does it by itself.
"""
import json
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any, Dict, List, Optional

from app.memory.journal import Journal, journal

LOOKBACK_DAYS = 42
_DAILY_DAYS = 5
_WEEKLY_WEEKS = 3
_SPREAD_MINUTES = 45   # how close to the usual time an action must be to count
_LEAD_MINUTES = 10     # heads-up this long before the usual time
_CACHE_SECONDS = 600
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _clock(minutes: int) -> str:
    hour, minute = divmod(int(minutes), 60)
    return datetime(2000, 1, 1, hour, minute).strftime("%I:%M %p").lstrip("0")


def find_habits(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Habits in a list of journal entries, most regular first."""
    times: Dict[tuple, List[datetime]] = defaultdict(list)
    labels: Dict[tuple, str] = {}
    for entry in entries:
        when = datetime.fromisoformat(entry["time"])
        for action in entry.get("actions", []):
            if not action.get("ok") or not action.get("capability"):
                continue
            key = (action["capability"], action.get("operation") or "", (action.get("target") or "").lower())
            times[key].append(when)
            labels[key] = action.get("label") or " ".join(p for p in key if p).replace("_", " ")

    habits = []
    for key, moments in times.items():
        for weekday in [None, *range(7)]:
            chosen = [m for m in moments if weekday is None or m.weekday() == weekday]
            if not chosen:
                continue
            usual = median(m.hour * 60 + m.minute for m in chosen)
            near = [m for m in chosen if abs(m.hour * 60 + m.minute - usual) <= _SPREAD_MINUTES]
            if weekday is None:
                count = len({m.date() for m in near})
                if count < _DAILY_DAYS:
                    continue
            else:
                count = len({m.isocalendar()[:2] for m in near})
                if count < _WEEKLY_WEEKS:
                    continue
            habits.append({
                "id": "|".join(key) + f"|{'daily' if weekday is None else weekday}",
                "capability": key[0], "operation": key[1], "target": key[2], "label": labels[key],
                "weekday": weekday, "minute": int(usual), "times": count,
                "description": f"{labels[key][:1].upper()}{labels[key][1:]} around {_clock(usual)}"
                               + (" most days" if weekday is None else f" on {_DAYS[weekday]}s"),
            })
    # A daily habit already covers the weekday versions of the same action.
    daily = {h["id"].rsplit("|", 1)[0] for h in habits if h["weekday"] is None}
    habits = [h for h in habits if h["weekday"] is None or h["id"].rsplit("|", 1)[0] not in daily]
    return sorted(habits, key=lambda h: -h["times"])


class Habits:
    def __init__(self, source: Journal = journal):
        self.journal = source
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cached_at = 0.0

    def all(self, today: Optional[date] = None) -> List[Dict[str, Any]]:
        if self._cache is None or time.time() - self._cached_at > _CACHE_SECONDS:
            since = (today or date.today()) - timedelta(days=LOOKBACK_DAYS)
            self._cache = find_habits(self.journal.all_entries(since=since))
            self._cached_at = time.time()
        return self._cache

    def forget(self) -> None:
        self._cache = None

    # The user can say "not a habit" in Settings > Memory; that habit is never suggested again.
    @property
    def _dismissed_path(self):
        return self.journal.folder.parent / "habits_dismissed.json"

    def dismissed(self) -> set:
        try:
            return set(json.loads(self._dismissed_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return set()

    def dismiss(self, habit_id: str) -> None:
        self._dismissed_path.parent.mkdir(parents=True, exist_ok=True)
        self._dismissed_path.write_text(json.dumps(sorted(self.dismissed() | {habit_id})), encoding="utf-8")

    def visible(self, today: Optional[date] = None) -> List[Dict[str, Any]]:
        hidden = self.dismissed()
        return [h for h in self.all(today) if h["id"] not in hidden]

    def due(self, now: datetime) -> List[Dict[str, Any]]:
        """Habits whose usual time is a few minutes away and that haven't happened yet today."""
        minute = now.hour * 60 + now.minute
        done_today = {(a.get("capability"), a.get("operation") or "", (a.get("target") or "").lower())
                      for e in self.journal.entries(now.date()) for a in e.get("actions", []) if a.get("ok")}
        return [h for h in self.visible(now.date())
                if (h["weekday"] is None or h["weekday"] == now.weekday())
                and 0 <= h["minute"] - minute <= _LEAD_MINUTES
                and (h["capability"], h["operation"], h["target"]) not in done_today]


habits = Habits()
