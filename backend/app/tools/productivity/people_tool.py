"""The people in the user's life: who they are, how to reach them, and their birthdays.

People are kept on this computer as structured records (not free-text memories),
because sending a message or an email needs an exact number or address. Messaging
is a HIGH-risk follow-up: the user sees the exact text and number first, and the
message is only sent when WhatsApp itself shows that text ready in that person's chat.
"""
import asyncio
import json
import os
import re
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.paths import data_path
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

_DRAFT_TTL = 600
_FIELDS = ("relation", "full_name", "email", "phone", "birthday")
# Country calling codes, for numbers saved without one (data, used with the computer's country).
_CALLING_CODES = {"IN": "91", "US": "1", "CA": "1", "GB": "44", "AU": "61", "AE": "971", "SG": "65",
                  "DE": "49", "FR": "33", "NZ": "64", "IE": "353", "ZA": "27", "SA": "966", "MY": "60"}
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def parse_birthday(value: Any) -> Optional[str]:
    """'1998-03-12', '--03-12', '03-12', '12 March', 'March 12th' -> 'YYYY-MM-DD' or '--MM-DD'."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        return _valid(year, month, day)
    match = re.fullmatch(r"-{0,2}(\d{1,2})[-/.](\d{1,2})", text)
    if match:
        first, second = int(match.group(1)), int(match.group(2))
        # "--MM-DD" as written by the interpreter; "20-10" can only be day-month.
        return _valid(None, second, first) if first > 12 else _valid(None, first, second)
    month = next((i + 1 for i, name in enumerate(_MONTHS) if re.search(rf"\b{name[:3]}", text)), None)
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    day = next((n for n in numbers if 1 <= n <= 31), None)
    year = next((n for n in numbers if n > 1900), None)
    return _valid(year, month, day) if month and day else None


def _valid(year: Optional[int], month: int, day: int) -> Optional[str]:
    try:
        date(year or 2000, month, day)  # 2000 is a leap year, so 29 Feb is allowed without a year
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}" if year else f"--{month:02d}-{day:02d}"


def next_birthday(birthday: str, today: date) -> Tuple[date, Optional[int]]:
    """The next date it falls on (today counts) and the age they'll turn, if the year is known."""
    month, day = int(birthday[-5:-3]), int(birthday[-2:])
    for year in (today.year, today.year + 1, today.year + 2):
        try:
            when = date(year, month, day)
        except ValueError:
            continue  # 29 February outside leap years
        if when >= today:
            born = int(birthday[:4]) if not birthday.startswith("--") else None
            return when, (when.year - born) if born else None
    raise ValueError(birthday)


def clean_phone(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    digits = re.sub(r"\D", "", text)
    international = text.startswith("+") or text.startswith("00")
    if text.startswith("00"):
        digits = digits[2:]  # 0044... is the same as +44...
    if not 7 <= len(digits) <= 15:
        return None
    return f"+{digits}" if international else digits


def whatsapp_number(phone: str, country: str) -> Optional[str]:
    """International digits for a WhatsApp link, adding the country code when it's missing."""
    if phone.startswith("+"):
        return phone[1:]
    code = _CALLING_CODES.get((country or "").upper())
    if code and len(phone) == 11 and phone.startswith("0"):
        return code + phone[1:]  # trunk prefix, e.g. 0 98765 43210
    if code and len(phone) == 10:
        return code + phone
    return None


class PeopleStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("people", "people.json")
        self._lock = threading.Lock()

    def load(self) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
            except (OSError, json.JSONDecodeError):
                return []

    def _save(self, people: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(people, indent=2, ensure_ascii=False), encoding="utf-8")

    def find(self, name: str) -> List[Dict[str, Any]]:
        """People the user could mean: by what they call them, full name or relation ("my mom")."""
        wanted = [w for w in _words(name) if w not in ("my", "the", "our")]
        if not wanted:
            return []
        exact, partial = [], []
        for person in self.load():
            labels = [person["name"], person.get("full_name", ""), person.get("relation", "")]
            if any(_words(label) == wanted for label in labels if label):
                exact.append(person)
            elif any(set(wanted) <= set(_words(label)) for label in labels if label):
                partial.append(person)
        return exact or partial

    def upsert(self, name: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        people = self.load()
        matches = self.find(name)
        person = next((p for p in people if matches and p["id"] == matches[0]["id"]), None)
        if person is None:
            person = {"id": uuid.uuid4().hex[:8], "name": name.strip(), "notes": []}
            people.append(person)
        note = changes.pop("note", None)
        person.update({k: v for k, v in changes.items() if v})
        if note and note not in person.setdefault("notes", []):
            person["notes"].append(note)
        person["updated"] = datetime.now().isoformat(timespec="seconds")
        self._save(people)
        return person

    def remove(self, person_id: str) -> None:
        self._save([p for p in self.load() if p["id"] != person_id])

    def labels(self) -> List[str]:
        """How the interpreter hears about them: 'Mom (Sunita Sharma)', 'Priya (best friend)'."""
        out = []
        for p in self.load():
            extra = p.get("full_name") or p.get("relation")
            out.append(f"{p['name']} ({extra})" if extra and extra.lower() != p["name"].lower() else p["name"])
        return out

    def birthdays(self, today: date, within_days: int = 7) -> List[Tuple[Dict[str, Any], date, Optional[int]]]:
        upcoming = []
        for person in self.load():
            if person.get("birthday"):
                when, age = next_birthday(person["birthday"], today)
                if (when - today).days <= within_days:
                    upcoming.append((person, when, age))
        return sorted(upcoming, key=lambda item: item[1])


people_store = PeopleStore()


def describe(person: Dict[str, Any], today: Optional[date] = None) -> str:
    today = today or date.today()
    parts = [person["name"]]
    if person.get("full_name") and person["full_name"].lower() != person["name"].lower():
        parts[0] += f" ({person['full_name']})"
    if person.get("relation") and person["relation"].lower() != person["name"].lower():
        parts.append(f"your {person['relation']}")
    details = []
    if person.get("phone"):
        details.append(f"phone {person['phone']}")
    if person.get("email"):
        details.append(f"email {person['email']}")
    if person.get("birthday"):
        details.append(f"birthday {birthday_text(person['birthday'], today)}")
    text = ", ".join(parts)
    if details:
        text += ": " + ", ".join(details)
    if person.get("notes"):
        text += ". " + "; ".join(person["notes"][-3:])
    return text + ("" if text.endswith(".") else ".")


def birthday_text(birthday: str, today: date) -> str:
    when, age = next_birthday(birthday, today)
    days = (when - today).days
    label = f"{when.day} {when:%B}"
    if days == 0:
        return f"today ({label})" + (f", turning {age}" if age else "")
    soon = "tomorrow" if days == 1 else f"in {days} days"
    return f"{label}, {soon}" + (f", turning {age}" if age else "")


@dataclass
class MessageDraft:
    person: Dict[str, Any]
    number: str            # international digits for the link
    text: str
    created: float


class PeopleTool(BaseTool):
    manifest = ToolManifest(
        name="people",
        display_name="People",
        description="Remembers the people in your life (relation, number, email, birthday) and messages them on WhatsApp with your approval.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["save_person", "person_info", "list_people", "forget_person", "message_person",
                      "remove_person", "send_message"],
        operations={"remember_person": "save_person", "person_info": "person_info", "list_people": "list_people",
                    "forget_person": "forget_person", "message": "message_person"},
        free_text_operations=["remember_person", "person_info", "forget_person", "message"],
        default_targets={"list_people": "people"},
        # Sending a message and forgetting someone only happen after the user's yes.
        operation_permissions={"send_message": PermissionLevel.HIGH, "remove_person": PermissionLevel.HIGH},
        ability="remember the people in your life and message them on WhatsApp",
        target_description=(
            "the person as the user calls them ('Mom', 'Priya'); only real people (family, friends, colleagues), never the "
            "user themselves, their likes or things. For remember_person, parameters hold only what the "
            "user said: relation (e.g. 'mother', 'best friend'), full_name, email, phone (keep any country code), "
            "birthday ('YYYY-MM-DD', or '--MM-DD' without a year) or note. For person_info, parameters.field is "
            "'phone', 'email' or 'birthday' when asked about one thing. For message, parameters.text is the exact "
            "message to send, written as the user would write it; it is sent on WhatsApp"
        ),
    )
    timeout_seconds = 60.0

    def __init__(self, store: PeopleStore = people_store):
        self.store = store
        self.draft: Optional[MessageDraft] = None
        self.pending_forget: Optional[Tuple[Dict[str, Any], float]] = None

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="People stored on this computer", dependencies=[])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        if operation == "list_people":
            return "people", 0.9
        found = self.store.find(text)
        if found and operation != "remember_person":
            return found[0]["name"], 0.95
        return (text, 0.7) if text else (None, 0.0)

    def describe_action(self, args: Dict[str, Any]) -> str:
        operation, target = args.get("operation"), str(args.get("target") or "").strip()
        if operation == "send_message" and self.draft:
            return f"send “{self.draft.text}” to {self.draft.person['name']} on WhatsApp"
        if operation == "remove_person" and self.pending_forget:
            return f"forget {self.pending_forget[0]['name']}"
        labels = {"remember_person": f"remember {target}", "person_info": f"look up {target}",
                  "list_people": "list the people you've told me about", "forget_person": f"forget {target}",
                  "message": f"write a message to {target}"}
        return labels.get(operation) or super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation = args.get("operation")
        if dry_run:
            return {"dry_run": True, "action": operation, "target": args.get("target")}
        handlers = {"remember_person": self._remember, "person_info": self._info, "list_people": self._list,
                    "forget_person": self._propose_forget, "remove_person": self._forget,
                    "message": self._propose_message}
        if operation == "send_message":
            return await self._send()
        handler = handlers.get(operation)
        if handler is None:
            return self._fail(f"I can't do '{operation}' with people")
        result = handler(args)
        return await result if asyncio.iscoroutine(result) else result

    # ------------------------------------------------------------- knowing people

    def _remember(self, args) -> Dict[str, Any]:
        name = str(args.get("target") or "").strip()
        if not name:
            return self._fail("Who is this about?")
        changes: Dict[str, Any] = {}
        problems = []
        for field in _FIELDS:
            value = args.get(field)
            if value in (None, ""):
                continue
            if field == "phone":
                value = clean_phone(value)
                if value is None:
                    problems.append("that phone number doesn't look complete")
                    continue
            elif field == "birthday":
                value = parse_birthday(value)
                if value is None:
                    problems.append("I couldn't read that birthday")
                    continue
            elif field == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value)):
                problems.append("that email address doesn't look right")
                continue
            changes[field] = str(value).strip()
        if args.get("note"):
            changes["note"] = str(args["note"]).strip()
        if not changes:
            return self._fail("; ".join(problems).capitalize() if problems else f"What should I remember about {name}?")
        person = self.store.upsert(name, changes)
        summary = f"Got it. {describe(person)}"
        if problems:
            summary += f" ({'; '.join(problems)}.)"
        return {"action": "save_person", "person": person["name"], "success": True,
                "verified": bool(self.store.find(person["name"])), "summary": summary, "error": None}

    def _who(self, name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        found = self.store.find(name)
        if not found:
            known = ", ".join(p["name"] for p in self.store.load()[:8])
            hint = f" I know: {known}." if known else " Tell me about them, like: Priya's birthday is 12 March."
            return None, f"I don't know anyone called {name} yet.{hint}"
        if len(found) > 1:
            return None, f"Do you mean {' or '.join(describe(p).split(':')[0] for p in found[:3])}?"
        return found[0], None

    def _info(self, args) -> Dict[str, Any]:
        person, problem = self._who(str(args.get("target") or ""))
        if person is None:
            return self._fail(problem)
        field = str(args.get("field") or "").lower()
        today = date.today()
        if field in ("phone", "number", "mobile"):
            summary = f"{person['name']}'s number is {person['phone']}." if person.get("phone") \
                else f"I don't have {person['name']}'s number yet."
        elif field == "email":
            summary = f"{person['name']}'s email is {person['email']}." if person.get("email") \
                else f"I don't have {person['name']}'s email yet."
        elif field == "birthday":
            summary = f"{person['name']}'s birthday is {birthday_text(person['birthday'], today)}." if person.get("birthday") \
                else f"I don't know {person['name']}'s birthday yet."
        else:
            summary = describe(person, today)
        return {"action": "person_info", "success": True, "verified": True, "summary": summary, "error": None}

    def _list(self, args) -> Dict[str, Any]:
        people = self.store.load()
        if not people:
            summary = "You haven't told me about anyone yet. Try: Mom's number is +91 98765 43210."
        else:
            summary = "People you've told me about:\n" + "\n".join(describe(p) for p in people)
        return {"action": "list_people", "success": True, "verified": True, "summary": summary, "error": None}

    def _propose_forget(self, args) -> Dict[str, Any]:
        person, problem = self._who(str(args.get("target") or ""))
        if person is None:
            return self._fail(problem)
        self.pending_forget = (person, time.time())
        question = f"Forget {person['name']} and everything you told me about them?"
        return {"action": "forget_person", "success": True, "verified": True, "summary": question, "error": None,
                "confirmation": {"capability": "remove_person", "operation": "remove_person",
                                 "target": person["name"], "question": question}}

    def _forget(self, args) -> Dict[str, Any]:
        if self.pending_forget is None or time.time() - self.pending_forget[1] > _DRAFT_TTL:
            return self._fail("there's nobody waiting to be forgotten")
        person = self.pending_forget[0]
        self.pending_forget = None
        self.store.remove(person["id"])
        return {"action": "remove_person", "success": True, "verified": not self.store.find(person["name"]),
                "summary": f"I've forgotten {person['name']}.", "error": None}

    # ------------------------------------------------------------- messaging

    async def _propose_message(self, args) -> Dict[str, Any]:
        instruction = str(args.get("instruction") or "").strip()
        draft = self._fresh_draft()
        target = str(args.get("target") or "").strip()
        if draft and instruction and (not target or target.lower() in ("it", "this", "the message")
                                      or self.store.find(target)[:1] == [draft.person]):
            text = await self._rewrite(draft.text, instruction)
            return self._propose(MessageDraft(draft.person, draft.number, text, time.time()))

        person, problem = self._who(target)
        if person is None:
            return self._fail(problem)
        if not person.get("phone"):
            return self._fail(f"I don't have {person['name']}'s number. Tell me, like: {person['name']}'s number is +91 98765 43210")
        from app.tools.web.weather import locator
        number = whatsapp_number(person["phone"], await locator.country_code())
        if number is None:
            return self._fail(f"{person['name']}'s number needs its country code (like +91) for WhatsApp. Tell me the full number")
        text = " ".join(str(args.get("text") or instruction or "").split()).strip("\"“”")
        if not text:
            return self._fail(f"What should I say to {person['name']}?")
        return self._propose(MessageDraft(person, number, text, time.time()))

    def _propose(self, draft: MessageDraft) -> Dict[str, Any]:
        self.draft = draft
        question = f"Send “{draft.text}” to {draft.person['name']} (+{draft.number}) on WhatsApp?"
        return {"action": "message_person", "success": True, "verified": True, "summary": question, "error": None,
                "confirmation": {"capability": "send_message", "operation": "send_message",
                                 "target": draft.person["name"], "question": question,
                                 "revise": {"capability": "message_person", "operation": "message", "target": "it"}}}

    async def _send(self) -> Dict[str, Any]:
        draft = self._fresh_draft()
        if draft is None:
            return self._fail("there's no message waiting to be sent. Ask me again")
        from app.tools.system import screen_reader
        if not screen_reader.IS_WINDOWS:
            return self._fail("sending WhatsApp messages works on Windows for now")
        self.draft = None
        link = f"whatsapp://send?phone={draft.number}&text={urllib.parse.quote(draft.text)}"
        try:
            os.startfile(link)  # the WhatsApp app opens that person's chat with the text typed in
        except OSError:
            return self._fail("WhatsApp doesn't seem to be installed. Install WhatsApp from the Microsoft Store")
        error = "WhatsApp didn't open"
        for _ in range(16):  # up to ~8 s for WhatsApp to start and load the chat
            await asyncio.sleep(0.5)
            window = await asyncio.to_thread(screen_reader.find_app_window, "whatsapp")
            if window is None:
                continue
            error = await asyncio.to_thread(screen_reader.send_prefilled, window, draft.text)
            if error is None:
                break
        if error:
            return self._fail(error)
        await asyncio.sleep(1.0)
        shown = await asyncio.to_thread(screen_reader.text_visible, window, draft.text)
        return {"action": "send_message", "success": True, "verified": shown,
                "summary": f"Sent to {draft.person['name']} on WhatsApp." if shown
                else f"I pressed send in WhatsApp, but couldn't see the message appear. Please check {draft.person['name']}'s chat.",
                "error": None if shown else "couldn't confirm the message appeared"}

    async def _rewrite(self, text: str, instruction: str) -> str:
        from app.cognition.llm.manager import RoleProvider
        result = await RoleProvider("conversation").generate_response(
            [{"role": "user", "content": f"My message: “{text}”\nChange it: {instruction}"}],
            "You rewrite a short chat message the user is about to send. Keep their voice and meaning, apply the change, "
            "never add facts. Output only the new message text, no quotes.")
        return " ".join(str(result.get("response", "")).split()).strip("\"“”") or text

    def _fresh_draft(self) -> Optional[MessageDraft]:
        if self.draft and time.time() - self.draft.created < _DRAFT_TTL:
            return self.draft
        return None

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


people_tool = PeopleTool()
tool_registry.register_tool(people_tool)
