"""The user's calendar: what's on, add an event, and move or delete one after approval.

Adding an event only touches the user's own calendar (no guests are invited), so it
happens straight away and is read back to verify. Moving or deleting an existing
event changes something the user made, so the tool proposes it and the router holds
the change until the user says yes ("change_event" is never an interpreter operation).
"""
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.dates import day_offset
from app.integrations.google.account import GoogleError, NotConnected
from app.integrations.google.calendar import Event, google_calendar
from app.tools import recent_results
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest
from app.tools.system.reminders import parse_due

_PROPOSAL_TTL = 600
_SEARCH_DAYS = 60


@dataclass
class Proposal:
    kind: str                  # "move" or "delete"
    event: Event
    start: Optional[datetime]  # new start, for "move"
    created: float


def clock(moment: datetime) -> str:
    return moment.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def when(moment: datetime, all_day: bool = False, today: Optional[date] = None) -> str:
    """'today at 5 PM', 'tomorrow', 'on Friday 23 October at 9:30 AM'."""
    today = today or date.today()
    days = (moment.date() - today).days
    day = "today" if days == 0 else "tomorrow" if days == 1 else "yesterday" if days == -1 \
        else f"on {moment:%A} {moment.day} {moment:%B}"
    return day if all_day else f"{day} at {clock(moment)}"


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" and {items[-1]}"


def describe_day(events: List[Event], label: str) -> str:
    if not events:
        return f"Nothing on your calendar {label}."
    items = [f"{e.title} (all day)" if e.all_day else f"{e.title} at {clock(e.start)}" for e in events[:8]]
    more = f", plus {len(events) - 8} more" if len(events) > 8 else ""
    count = "one event" if len(events) == 1 else f"{len(events)} events"
    return f"{label.capitalize()} you have {count}: {_join(items)}{more}."


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def best_matches(events: List[Event], words: str) -> List[Event]:
    """Events sharing the most words with what the user called it (all ties)."""
    wanted = _words(words)
    scored = [(len(wanted & _words(e.title)), e) for e in events]
    top = max((score for score, _ in scored), default=0)
    return [e for score, e in scored if top and score == top]


class CalendarTool(BaseTool):
    manifest = ToolManifest(
        name="calendar",
        display_name="Calendar",
        description="Reads your calendar, adds events, and moves or deletes them with your approval.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["calendar_agenda", "create_event", "move_event", "delete_event", "change_event"],
        operations={"agenda": "calendar_agenda", "schedule": "create_event",
                    "reschedule": "move_event", "unschedule": "delete_event"},
        free_text_operations=["agenda", "schedule", "reschedule", "unschedule"],
        default_targets={"agenda": "today"},
        operation_permissions={"schedule": PermissionLevel.MEDIUM, "change_event": PermissionLevel.HIGH},
        ability="check your calendar and add, move or cancel events",
        target_description=(
            "for agenda: the day ('today', 'tomorrow', a weekday or 'YYYY-MM-DD'); "
            "for schedule: the event's title, with parameters.at (start, 'HH:MM' today or 'YYYY-MM-DDTHH:MM'; "
            "'YYYY-MM-DD' for an all-day event) and optional parameters.duration_minutes; "
            "for reschedule: words from the event's title, with parameters.at for the new start; "
            "for unschedule: words from the event's title"
        ),
    )
    timeout_seconds = 30.0

    def __init__(self, calendar=google_calendar):
        self.calendar = calendar
        self.proposal: Optional[Proposal] = None

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Google Calendar (sign in under Settings > Accounts)", dependencies=["httpx"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        if operation == "agenda":
            return text or "today", 0.8
        return (text, 0.7) if text else (None, 0.0)

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        operation = args.get("operation")
        if operation in ("schedule", "reschedule") and self._start(args) is None:
            return False, "When should it be? For example 'tomorrow at 5 pm'."
        return True, None

    def describe_action(self, args: Dict[str, Any]) -> str:
        if args.get("operation") == "change_event" and self.proposal:
            event = self.proposal.event
            if self.proposal.kind == "delete":
                return f"delete “{event.title}” {when(event.start, event.all_day)} from your calendar"
            return f"move “{event.title}” to {when(self.proposal.start, event.all_day)}"
        return super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation = args.get("operation")
        try:
            if operation == "agenda":
                return await self._agenda(args)
            if operation == "schedule":
                return await self._schedule(args, dry_run)
            if operation in ("reschedule", "unschedule"):
                return await self._propose(args, operation)
            if operation == "change_event":
                return await self._apply(dry_run)
        except (NotConnected, GoogleError) as problem:
            return self._fail(str(problem))
        return self._fail(f"I can't do '{operation}' with the calendar")

    # ------------------------------------------------------------- operations

    async def _agenda(self, args) -> Dict[str, Any]:
        today = date.today()
        offset = day_offset(args.get("target") or args.get("day"), today)
        if offset is None:
            return self._fail("Which day? For example today, tomorrow or Friday")
        day = today + timedelta(days=offset)
        events = await self.calendar.day(day)
        label = "today" if offset == 0 else "tomorrow" if offset == 1 else f"on {day:%A} {day.day} {day:%B}"
        recent_results.remember("calendar", [{"url": e.link, "title": e.title} for e in events if e.link])
        return {"action": "calendar_agenda", "events": [e.title for e in events], "success": True,
                "verified": True, "summary": describe_day(events, label), "error": None}

    async def _schedule(self, args, dry_run: bool) -> Dict[str, Any]:
        title = str(args.get("target") or "").strip().strip("\"“”") or "Event"
        start, all_day = self._start(args), self._all_day(args)
        minutes = self._number(args.get("duration_minutes")) or 60
        end = start + (timedelta(days=1) if all_day else timedelta(minutes=minutes))
        if dry_run:
            return {"dry_run": True, "action": "create_event", "title": title, "start": start.isoformat()}

        clashes = [e for e in await self.calendar.events(start, end) if not e.all_day and not all_day]
        created = await self.calendar.create(title, start, end, all_day)
        stored = await self.calendar.get(created.id)
        verified = stored is not None and stored.start == created.start
        summary = f"Added “{title}” to your calendar {when(start, all_day)}."
        if clashes:
            summary += f" Heads up: it overlaps with {_join([e.title for e in clashes[:3]])}."
        return {"action": "create_event", "event_id": created.id, "success": True, "verified": verified,
                "summary": summary, "error": None if verified else "couldn't read the new event back"}

    async def _propose(self, args, operation: str) -> Dict[str, Any]:
        now = datetime.now()
        upcoming = await self.calendar.events(now.replace(hour=0, minute=0), now + timedelta(days=_SEARCH_DAYS), limit=250)
        matches = best_matches(upcoming, str(args.get("target") or ""))
        if not matches:
            return self._fail(f"I couldn't find “{args.get('target')}” on your calendar in the next {_SEARCH_DAYS} days")
        if len(matches) > 1:
            options = "; ".join(f"{e.title} {when(e.start, e.all_day)}" for e in matches[:4])
            return self._fail(f"A few events match: {options}. Which one?")
        event = matches[0]
        if operation == "reschedule":
            start = self._start(args, base=event.start)
            self.proposal = Proposal("move", event, start, time.time())
            question = f"Move “{event.title}” from {when(event.start, event.all_day)} to {when(start, event.all_day)}?"
        else:
            self.proposal = Proposal("delete", event, None, time.time())
            question = f"Delete “{event.title}” {when(event.start, event.all_day)} from your calendar?"
        return {"action": "move_event" if operation == "reschedule" else "delete_event", "success": True,
                "verified": True, "summary": question, "error": None,
                "confirmation": {"capability": "change_event", "operation": "change_event",
                                 "target": event.title, "question": question}}

    async def _apply(self, dry_run: bool) -> Dict[str, Any]:
        proposal = self.proposal
        if proposal is None or time.time() - proposal.created > _PROPOSAL_TTL:
            return self._fail("there's no calendar change waiting. Ask me again")
        if dry_run:
            return {"dry_run": True, "action": "change_event", "kind": proposal.kind, "event": proposal.event.title}
        self.proposal = None
        event = proposal.event
        if proposal.kind == "delete":
            await self.calendar.delete(event)
            verified = await self.calendar.get(event.id) is None
            summary = f"Deleted “{event.title}”."
        else:
            moved = await self.calendar.move(event, proposal.start)
            stored = await self.calendar.get(moved.id)
            verified = stored is not None and stored.start == proposal.start
            summary = f"Moved “{event.title}” to {when(proposal.start, event.all_day)}."
        return {"action": "change_event", "success": True, "verified": verified, "summary": summary,
                "error": None if verified else "couldn't confirm the change on your calendar"}

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _all_day(args) -> bool:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(args.get("at") or "").strip()))

    def _start(self, args, base: Optional[datetime] = None) -> Optional[datetime]:
        at = str(args.get("at") or "").strip()
        if self._all_day(args):
            return datetime.fromisoformat(at)
        start = parse_due(args)
        if start is None or base is None or "T" in at:
            return start
        # "move it to 6" keeps the event's own day when a bare clock time is given.
        moved = base.replace(hour=start.hour, minute=start.minute)
        return moved

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        return float(match.group()) if match and float(match.group()) > 0 else None

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


calendar_tool = CalendarTool()
tool_registry.register_tool(calendar_tool)
