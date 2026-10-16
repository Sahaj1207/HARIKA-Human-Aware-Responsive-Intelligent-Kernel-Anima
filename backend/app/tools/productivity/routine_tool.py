"""Routines: the user's own named sequences of actions ("good night" -> mute, close Chrome, alarm at 7).

A routine is made by interpreting the user's description once with the same semantic
interpreter as any request; only steps that resolve to registered capabilities are
kept, and the routine is saved only after the user approves the exact list. Running a
routine does not happen here: the Cognitive Core expands it into ordinary action-graph
steps, so permissions, confirmations, progress and verification all apply as usual.
"""
import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.paths import data_path
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

_DRAFT_TTL = 900
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
# Routine operations never go inside a routine (no routines running routines).
_ROUTINE_OPERATIONS = {"create_routine", "run_routine", "list_routines", "delete_routine"}


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", (text or "").lower()))


def parse_days(value: Any) -> Optional[List[int]]:
    """'every day', 'weekdays', 'weekends', 'monday and friday', ['sat','sun'] -> weekday numbers (Mon=0)."""
    if value in (None, "", []):
        return None
    text = " ".join(value) if isinstance(value, list) else str(value)
    text = text.lower()
    if re.search(r"\b(daily|every ?day|everyday|each day)\b", text):
        return list(range(7))
    if "weekday" in text:
        return [0, 1, 2, 3, 4]
    if "weekend" in text:
        return [5, 6]
    days = sorted({i for i, name in enumerate(_WEEKDAYS) if re.search(rf"\b{name[:3]}", text)})
    return days or None


def describe_days(days: List[int]) -> str:
    if days == list(range(7)):
        return "every day"
    if days == [0, 1, 2, 3, 4]:
        return "every weekday"
    if days == [5, 6]:
        return "every weekend"
    names = [_WEEKDAYS[d].capitalize() for d in days]
    return "every " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}")


def describe_time(at: str) -> str:
    return datetime.strptime(at, "%H:%M").strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


class RoutineStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("routines", "routines.json")
        self._lock = threading.Lock()

    def load(self) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            except (OSError, json.JSONDecodeError):
                return []

    def _save(self, routines: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(routines, indent=2), encoding="utf-8")

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        key = normalize(name)
        return next((r for r in self.load() if normalize(r["name"]) == key), None)

    def put(self, routine: Dict[str, Any]) -> None:
        key = normalize(routine["name"])
        self._save([r for r in self.load() if normalize(r["name"]) != key] + [routine])

    def delete(self, name: str) -> bool:
        key = normalize(name)
        routines = self.load()
        kept = [r for r in routines if normalize(r["name"]) != key]
        self._save(kept)
        return len(kept) < len(routines)

    def mark_run(self, name: str, day: str) -> None:
        routines = self.load()
        for routine in routines:
            if normalize(routine["name"]) == normalize(name):
                routine["last_run"] = day
        self._save(routines)

    def names(self) -> List[str]:
        return [r["name"] for r in self.load()]

    def match_trigger(self, message: str) -> Optional[Dict[str, Any]]:
        """The routine whose name is exactly what the user said ("Good night!" -> "good night")."""
        said = normalize(message)
        return next((r for r in self.load() if said and normalize(r["name"]) == said), None) if said else None

    def best_match(self, name: str) -> Optional[Dict[str, Any]]:
        """A routine named like `name`: exact, or every word of one inside the other ("my good night routine")."""
        exact = self.get(name)
        if exact:
            return exact
        said = set(normalize(name).split()) - {"routine", "my", "the", "mode"}
        for routine in self.load():
            words = set(normalize(routine["name"]).split()) - {"routine", "my", "the", "mode"}
            if words and words <= said:
                return routine
        return None


routine_store = RoutineStore()


@dataclass
class RoutineDraft:
    routine: Dict[str, Any]
    description: str        # what the user asked for, kept so changes can be applied to it
    created: float


def step_label(step: Dict[str, Any]) -> str:
    """'mute the volume', 'open Chrome' — from the step's own tool."""
    tool = tool_registry.get_tool(step.get("tool_name") or "")
    args = {"operation": step["operation"], "target": step.get("target"), **(step.get("parameters") or {})}
    try:
        return tool.describe_action(args) if tool else f"{step['operation']} {step.get('target') or ''}".strip()
    except Exception:
        return f"{step['operation']} {step.get('target') or ''}".strip()


def step_needs_approval(step: Dict[str, Any]) -> bool:
    tool = tool_registry.get_tool(step.get("tool_name") or "")
    if tool is None:
        return True
    level = tool.manifest.operation_permissions.get(step["operation"], tool.manifest.permissions)
    return level is PermissionLevel.HIGH


class RoutineTool(BaseTool):
    manifest = ToolManifest(
        name="routines",
        display_name="Routines",
        description="Saves named routines (a phrase that runs several actions, optionally on a schedule), runs, lists and deletes them.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["create_routine", "run_routine", "list_routines", "delete_routine", "save_routine", "remove_routine"],
        operations={"create_routine": "create_routine", "run_routine": "run_routine",
                    "list_routines": "list_routines", "delete_routine": "delete_routine"},
        free_text_operations=["create_routine", "run_routine", "delete_routine"],
        default_targets={"list_routines": "routines"},
        # Saving or deleting a routine changes standing behaviour, so it waits for a yes.
        operation_permissions={"save_routine": PermissionLevel.HIGH, "remove_routine": PermissionLevel.HIGH},
        ability="save routines: one phrase (or a time) that runs several actions",
        target_description=(
            "for create_routine: the routine's short name, which is also the phrase that runs it (e.g. 'good night'), "
            "with parameters.steps describing in plain words what it should do, in order, and optionally "
            "parameters.at ('HH:MM') and parameters.days ('every day', 'weekdays', 'weekends' or weekday names) to run it on a schedule; "
            "for run_routine and delete_routine: the routine's name"
        ),
    )
    timeout_seconds = 90.0

    def __init__(self, store: RoutineStore = routine_store, interpreter=None):
        self.store = store
        self._interpreter = interpreter
        self.draft: Optional[RoutineDraft] = None
        self.pending_delete: Optional[Tuple[str, float]] = None

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Routines stored on this computer", dependencies=[])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        if operation == "list_routines":
            return "routines", 0.9
        if operation in ("run_routine", "delete_routine"):
            routine = self.store.best_match(text)
            return (routine["name"], 0.95) if routine else ((text, 0.5) if text else (None, 0.0))
        return (text, 0.7) if text else (None, 0.0)

    def describe_action(self, args: Dict[str, Any]) -> str:
        if args.get("operation") == "save_routine" and self.draft:
            return f"save the routine “{self.draft.routine['name']}”"
        if args.get("operation") == "remove_routine" and self.pending_delete:
            return f"delete the routine “{self.pending_delete[0]}”"
        if args.get("operation") == "run_routine":
            return f"run “{args.get('target')}”"
        return super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation = args.get("operation")
        if dry_run:
            return {"dry_run": True, "action": operation, "target": args.get("target")}
        if operation == "create_routine":
            return await self._create(args)
        if operation == "save_routine":
            return self._save()
        if operation == "list_routines":
            return self._list()
        if operation == "delete_routine":
            return self._propose_delete(str(args.get("target") or ""))
        if operation == "remove_routine":
            return self._delete()
        if operation == "run_routine":
            # Reached only when no saved routine matched; real runs are expanded by the Cognitive Core.
            return self._fail(self._unknown(str(args.get("target") or "")))
        return self._fail(f"I can't do '{operation}' with routines")

    # ------------------------------------------------------------- creating

    async def _create(self, args) -> Dict[str, Any]:
        name = str(args.get("target") or "").strip().strip("\"“”")
        instruction = str(args.get("instruction") or "").strip()
        draft = self._fresh_draft()
        if draft and instruction and (not name or normalize(name) in ("it", "the routine", normalize(draft.routine["name"]))):
            # "also open Spotify" / "drop the reminder": change the routine being set up.
            description = f"{draft.description}. Then apply this change: {instruction}"
            name, schedule = draft.routine["name"], draft.routine.get("schedule")
        else:
            description = str(args.get("steps") or instruction or "").strip()
            schedule = None
        if not name:
            return self._fail("What should the routine be called? That's also what you'll say to run it")
        if not description:
            return self._fail(f"What should “{name}” do? For example: mute the volume and close Chrome")

        if args.get("at") or args.get("days"):
            at = str(args.get("at") or "").strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self._fail("What time should it run? For example 7:30 am")
            schedule = {"at": f"{int(at.split(':')[0]):02d}:{at.split(':')[1]}",
                        "days": parse_days(args.get("days")) or list(range(7))}

        steps, problem = await self._steps(description)
        if problem and not steps:
            return self._fail(problem)
        if schedule:
            risky = [s for s in steps if step_needs_approval(s)]
            if risky:
                steps = [s for s in steps if s not in risky]
                problem = (problem + " " if problem else "") + (
                    f"I left out {', '.join(step_label(s) for s in risky)}: a scheduled routine runs while you might be away, "
                    "so it can't include steps that need your OK.")
            if not steps:
                return self._fail(problem)

        routine = {"name": name, "steps": steps, "schedule": schedule, "last_run": "",
                   "created": datetime.now().isoformat(timespec="seconds")}
        self.draft = RoutineDraft(routine, description, time.time())
        return self._propose(routine, problem)

    async def _steps(self, description: str) -> Tuple[List[Dict[str, Any]], str]:
        """Interpret the description into supported, structured steps (nothing runs here)."""
        interpreter = self._interpreter
        if interpreter is None:
            from app.cognition.core import cognitive_core
            interpreter = cognitive_core._interpreter()
        try:
            request = await interpreter.interpret(description, timeout=90.0)
        except Exception:
            return [], "I couldn't work out the steps just now. Try again in a moment"
        steps = [
            {"operation": s.operation, "target": s.target, "parameters": dict(s.parameters), "tool_name": s.tool_name}
            for s in request.steps if s.operation not in _ROUTINE_OPERATIONS
        ]
        for step in steps:
            step["label"] = step_label(step)
        problem = ""
        if request.clarification_question and request.validation_error:
            problem = request.clarification_question.replace("I understood that you want me to", "I can't").replace(
                ", but I don't have a way to do that yet.", " yet, so I left it out.")
        if not steps:
            return [], problem or "I couldn't turn that into actions I can do. Try naming them, like: mute and open Spotify"
        return steps, problem

    def _propose(self, routine: Dict[str, Any], note: str = "") -> Dict[str, Any]:
        lines = "\n".join(f"{i}. {s['label']}" for i, s in enumerate(routine["steps"], 1))
        when = f"When you say “{routine['name']}”"
        if routine.get("schedule"):
            schedule = routine["schedule"]
            when += f", and {describe_days(schedule['days'])} at {describe_time(schedule['at'])}"
        replacing = " (this replaces your current one)" if self.store.get(routine["name"]) else ""
        question = f"{when}, I'll:\n{lines}\n\n" + (f"{note}\n\n" if note else "") + \
            f"Save the routine “{routine['name']}”{replacing}?"
        return {"action": "create_routine", "routine": routine["name"], "success": True, "verified": True,
                "summary": question, "error": None,
                "confirmation": {"capability": "save_routine", "operation": "save_routine",
                                 "target": routine["name"], "question": question,
                                 "revise": {"capability": "create_routine", "operation": "create_routine",
                                            "target": routine["name"]}}}

    def _save(self) -> Dict[str, Any]:
        draft = self._fresh_draft()
        if draft is None:
            return self._fail("there's no routine waiting to be saved. Describe it again")
        self.store.put(draft.routine)
        self.draft = None
        saved = self.store.get(draft.routine["name"]) is not None
        return {"action": "save_routine", "success": True, "verified": saved,
                "summary": f"Saved. Say “{draft.routine['name']}” whenever you want it.", "error": None}

    # ------------------------------------------------------------- the rest

    def _list(self) -> Dict[str, Any]:
        routines = self.store.load()
        if not routines:
            return {"action": "list_routines", "success": True, "verified": True, "error": None,
                    "summary": "You don't have any routines yet. Try: when I say good night, mute and close Chrome."}
        lines = []
        for r in routines:
            when = f" ({describe_days(r['schedule']['days'])} at {describe_time(r['schedule']['at'])})" if r.get("schedule") else ""
            lines.append(f"“{r['name']}”{when}: " + ", ".join(s.get("label", s["operation"]) for s in r["steps"]))
        return {"action": "list_routines", "success": True, "verified": True, "error": None,
                "summary": "Your routines:\n" + "\n".join(lines)}

    def _propose_delete(self, name: str) -> Dict[str, Any]:
        routine = self.store.best_match(name)
        if routine is None:
            return self._fail(self._unknown(name))
        self.pending_delete = (routine["name"], time.time())
        question = f"Delete the routine “{routine['name']}”?"
        return {"action": "delete_routine", "success": True, "verified": True, "summary": question, "error": None,
                "confirmation": {"capability": "remove_routine", "operation": "remove_routine",
                                 "target": routine["name"], "question": question}}

    def _delete(self) -> Dict[str, Any]:
        if self.pending_delete is None or time.time() - self.pending_delete[1] > _DRAFT_TTL:
            return self._fail("there's no routine waiting to be deleted")
        name = self.pending_delete[0]
        self.pending_delete = None
        self.store.delete(name)
        return {"action": "remove_routine", "success": True, "verified": self.store.get(name) is None,
                "summary": f"Deleted the routine “{name}”.", "error": None}

    def _unknown(self, name: str) -> str:
        names = self.store.names()
        if not names:
            return f"You don't have a routine called “{name}” yet. Tell me what it should do and I'll set it up"
        return f"You don't have a routine called “{name}”. Your routines are: {', '.join(names)}"

    def _fresh_draft(self) -> Optional[RoutineDraft]:
        if self.draft and time.time() - self.draft.created < _DRAFT_TTL:
            return self.draft
        return None

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


routine_tool = RoutineTool()
tool_registry.register_tool(routine_tool)


_MISSED_WINDOW_MINUTES = 30  # a routine missed while the computer slept still runs, within reason


def routine_due(routine: Dict[str, Any], now: datetime) -> bool:
    schedule = routine.get("schedule")
    if not schedule or now.weekday() not in schedule["days"] or routine.get("last_run") == now.date().isoformat():
        return False
    hour, minute = (int(part) for part in schedule["at"].split(":"))
    start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return 0 <= (now - start).total_seconds() < _MISSED_WINDOW_MINUTES * 60


async def run_routine_scheduler(interval_seconds: float = 20.0) -> None:
    """Run scheduled routines through the router, exactly as if the user had said their name."""
    import asyncio
    import logging

    from app.core.live_events import live_events
    from app.tools.system.reminders import show_os_notification

    logger = logging.getLogger("harika.tools.routines")
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            now = datetime.now()
            for routine in routine_store.load():
                if not routine_due(routine, now):
                    continue
                routine_store.mark_run(routine["name"], now.date().isoformat())
                from app.router.manager import router_manager
                result = await router_manager.route_request(routine["name"], user_id="routines")
                text = result.get("response", "")
                live_events.publish("routine", name=routine["name"], text=text)
                await asyncio.to_thread(show_os_notification, "HARIKA", f"Ran “{routine['name']}”. {text}"[:250])
                logger.info(f"[Routines] Ran scheduled routine '{routine['name']}'.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[Routines] Scheduled routine failed: {exc}")
