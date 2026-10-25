"""Google Calendar (the user's primary calendar) as plain events in local time."""
import asyncio
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.integrations.google.account import GoogleAccount, google_account

logger = logging.getLogger("harika.google.calendar")
_TODAY_REFRESH_SECONDS = 600

_EVENTS = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


@dataclass
class Event:
    id: str
    title: str
    start: datetime          # local time; midnight for all-day events
    end: datetime
    all_day: bool = False
    link: str = ""
    location: str = ""
    meeting_url: str = ""    # video call link (Meet, Zoom, Teams...), if the event has one

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start < end and start < self.end


def _local(moment: datetime) -> str:
    """Naive local time -> RFC 3339 with this computer's offset."""
    return moment.astimezone().isoformat(timespec="seconds")


def _parse_time(value: Dict[str, str]) -> datetime:
    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    return datetime.combine(date.fromisoformat(value["date"]), datetime.min.time())


_URL = re.compile(r"https://[^\s<>\"')]+")


def meeting_url(item: Dict[str, Any]) -> str:
    """The event's video call: Google's conference link, else the first web link in its location or notes."""
    if item.get("hangoutLink"):
        return item["hangoutLink"]
    for entry in (item.get("conferenceData") or {}).get("entryPoints", []):
        if entry.get("entryPointType") == "video" and str(entry.get("uri", "")).startswith("https://"):
            return entry["uri"]
    for text in (item.get("location", ""), item.get("description", "")):
        match = _URL.search(text or "")
        if match:
            return match.group(0).rstrip(".,;")
    return ""


def to_event(item: Dict[str, Any]) -> Event:
    return Event(
        id=item["id"],
        title=item.get("summary") or "(no title)",
        start=_parse_time(item["start"]),
        end=_parse_time(item["end"]),
        all_day="date" in item["start"],
        link=item.get("htmlLink", ""),
        location=item.get("location", ""),
        meeting_url=meeting_url(item),
    )


class GoogleCalendar:
    def __init__(self, account: GoogleAccount = google_account):
        self.account = account
        self._today: tuple = (0.0, None, [])  # (when read, which day, events)
        self._refreshing = False

    def cached_today(self) -> List[Event]:
        """Today's events from the last look, without waiting on the network: a stale or missing copy is
        refreshed in the background (at most every ten minutes, or after a change)."""
        read_at, day, events = self._today
        if (time.time() - read_at > _TODAY_REFRESH_SECONDS or day != date.today()) and not self._refreshing:
            try:
                connected = self.account.status()["calendar"]
                loop = asyncio.get_running_loop() if connected else None
            except Exception:  # no event loop here, or the account is unreadable
                loop = None
            if loop is not None:
                self._refreshing = True
                loop.create_task(self._refresh_today())
        return events if day == date.today() else []

    async def _refresh_today(self) -> None:
        try:
            self._today = (time.time(), date.today(), await self.day(date.today()))
        except Exception as exc:
            logger.info(f"[Calendar] Today's events unavailable: {exc}")
            self._today = (time.time(), self._today[1], self._today[2])
        finally:
            self._refreshing = False

    def _changed(self) -> None:
        self._today = (0.0, self._today[1], self._today[2])  # read again on next use

    async def events(self, start: datetime, end: datetime, query: str = "", limit: int = 50) -> List[Event]:
        self.account.require("calendar")
        params = {"timeMin": _local(start), "timeMax": _local(end), "singleEvents": "true",
                  "orderBy": "startTime", "maxResults": str(limit)}
        if query:
            params["q"] = query
        data = await self.account.request("GET", f"{_EVENTS}?{urllib.parse.urlencode(params)}")
        return [to_event(item) for item in data.get("items", []) if item.get("status") != "cancelled"]

    async def day(self, day: date) -> List[Event]:
        start = datetime.combine(day, datetime.min.time())
        return await self.events(start, start + timedelta(days=1))

    async def get(self, event_id: str) -> Optional[Event]:
        self.account.require("calendar")
        item = await self.account.request("GET", f"{_EVENTS}/{urllib.parse.quote(event_id)}")
        return None if not item or item.get("status") == "cancelled" else to_event(item)

    async def create(self, title: str, start: datetime, end: datetime, all_day: bool = False) -> Event:
        """Adds an event to the user's own calendar. No attendees, so nobody is invited or emailed."""
        self.account.require("calendar")
        body = {"summary": title}
        if all_day:
            body.update(start={"date": start.date().isoformat()}, end={"date": end.date().isoformat()})
        else:
            body.update(start={"dateTime": _local(start)}, end={"dateTime": _local(end)})
        created = to_event(await self.account.request("POST", _EVENTS, json=body))
        self._changed()
        return created

    async def move(self, event: Event, start: datetime) -> Event:
        self.account.require("calendar")
        end = start + (event.end - event.start)
        if event.all_day:
            body = {"start": {"date": start.date().isoformat()}, "end": {"date": end.date().isoformat()}}
        else:
            body = {"start": {"dateTime": _local(start)}, "end": {"dateTime": _local(end)}}
        item = await self.account.request("PATCH", f"{_EVENTS}/{urllib.parse.quote(event.id)}?sendUpdates=none", json=body)
        self._changed()
        return to_event(item)

    async def delete(self, event: Event) -> None:
        self.account.require("calendar")
        await self.account.request("DELETE", f"{_EVENTS}/{urllib.parse.quote(event.id)}?sendUpdates=none")
        self._changed()


google_calendar = GoogleCalendar()
