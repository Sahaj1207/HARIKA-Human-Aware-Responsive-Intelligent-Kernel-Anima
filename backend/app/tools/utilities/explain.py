"""HARIKA explaining herself: "how did you know that?", "did that go online?", "what did you do today?",
"did you send the reply to Ananya?".

Everything said here comes from records, never from the model's imagination: the notes kept
for her last reply (app/core/provenance.py: the abilities that ran, which AI service answered,
whether remembered facts were used) and the Activity log (app/memory/activity.py). The
presence layer may then say it in her own voice; the facts stay as they are.
"""
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_FILLER = {"the", "a", "an", "to", "my", "me", "you", "did", "about", "that", "this", "for", "on", "of", "and", "your"}


def past_day(text: str, today: date) -> Optional[date]:
    """'today', 'yesterday', 'monday' (the last one), '2026-11-10'."""
    words = (text or "today").strip().lower()
    if words in ("", "today", "now"):
        return today
    if words == "yesterday":
        return today - timedelta(days=1)
    for index, name in enumerate(_WEEKDAYS):
        if name in words:
            back = (today.weekday() - index) % 7
            return today - timedelta(days=back)
    try:
        return date.fromisoformat(words)
    except ValueError:
        return None


def _best_match(entries: List[Dict[str, Any]], about: str) -> Optional[Dict[str, Any]]:
    """The latest entry sharing most of what they asked about ("the reply to Ananya" finds "send ... to Ananya")."""
    words = {w for w in re.findall(r"[a-z0-9]+", about.lower()) if w not in _FILLER}
    best, best_score = None, 0
    for entry in entries:  # newest first, so ties go to the latest
        mine = set(re.findall(r"[a-z0-9]+", f"{entry['what']} {entry['detail']}".lower()))
        score = len(words & mine)
        if score > best_score and score * 2 >= len(words):
            best, best_score = entry, score
    return best


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _clock(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%I:%M %p").lstrip("0")


def _service_name(service_id: str) -> str:
    from app.cognition.llm.catalog import get_service
    service = get_service(service_id)
    if service is None:
        return service_id
    return "the AI model on this PC" if service.on_device else service.name


class ExplainTool(BaseTool):
    manifest = ToolManifest(
        name="explain",
        display_name="Explaining herself",
        description="Says how HARIKA knew what she just said and where the user's information went, and what she has done.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="utilities",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["explain_reply", "recall_activity"],
        operations={"how_i_knew": "explain_reply", "what_i_did": "recall_activity"},
        free_text_operations=["how_i_knew", "what_i_did"],
        default_targets={"how_i_knew": "last reply", "what_i_did": "today"},
        ability="tell you how I knew something, whether it went online, and what I've done for you",
        target_description=(
            "how_i_knew: questions about HARIKA's last reply (how she knew, where it came from, whether anything went "
            "online); target 'last reply'. what_i_did: what HARIKA herself did; target the day ('today', 'yesterday', "
            "a weekday), with parameters.about for one thing they ask about ('the reply to Ananya', 'dentist reminder')"
        ),
    )
    timeout_seconds = 5.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Answers from HARIKA's own records")

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        return (requested or ("today" if operation == "what_i_did" else "last reply")).strip(), 0.9

    def describe_action(self, args: Dict[str, Any]) -> str:
        return "look back at what I did" if args.get("operation") == "what_i_did" else "explain my last answer"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        from app.core import provenance
        provenance.skip()  # explaining isn't something to explain later
        if args.get("operation") == "what_i_did":
            text = self.what_i_did(str(args.get("target") or "today"), str(args.get("about") or ""))
        else:
            text = self.how_i_knew(provenance.last_reply())
        # Looking back isn't an action of its own, so it stays out of Settings > Activity.
        return {"action": "explain", "success": True, "verified": True, "summary": text, "not_activity": True}

    # ------------------------------------------------------------- "how did you know that?"

    @staticmethod
    def how_i_knew(notes: Optional[Dict[str, Any]]) -> str:
        if not notes:
            return "I haven't answered anything yet since I started, so there's nothing to explain."
        abilities = notes.get("abilities", [])
        used = [a["uses"] for a in abilities if a.get("uses")]
        sent = [a["sends_to"] for a in abilities if a.get("sends_to")]
        sources = []
        if used:
            sources.append(f"I looked at {_join(used)}")
        if notes.get("memories"):
            sources.append("I went by what you've told me before")
        if not sources and sent:
            sources.append(f"I looked it up with {_join(sent)}")
            sent = []  # said already
        if not sources:
            sources.append("That came from what I know in general, not from anything of yours")
        first = "; ".join(sources) + "."

        services: List[str] = []
        backups: List[str] = []
        for answer in notes.get("ai", []):
            name = _service_name(answer["service"])
            if name not in services:
                services.append(name)
            if answer.get("backup_for"):
                backups.append(f"{_service_name(answer['backup_for'])} was busy, so {name} answered")
        online = [s for s in services if s != "the AI model on this PC"]
        if online:
            where = f"Your message went to {_join(online)} to work it out"
            where += f", and I asked {_join(sent)}" if sent else ""
            where += ". Nothing else left your PC."
        elif sent:
            where = f"I asked {_join(sent)}; everything else stayed on your PC."
        else:
            where = "Everything stayed on your PC."
        return " ".join([first, where] + [f"({b}.)" for b in backups[:1]])

    # ------------------------------------------------------------- "what did you do today?"

    @staticmethod
    def what_i_did(day_text: str, about: str, today: Optional[date] = None) -> str:
        from app.memory.activity import DECLINED, EXPIRED, activity_log

        today = today or date.today()
        day = past_day(day_text, today)
        if day is None:
            return "I didn't catch which day you mean."
        if not activity_log.keeping():
            return "I'm not keeping an activity history (it's off in Settings > Activity), so I can't look back."
        back = (today - day).days
        entries = [e for e in activity_log.entries(back + 1) if e["time"].startswith(day.isoformat())]
        label = "today" if back == 0 else "yesterday" if back == 1 else f"on {day:%A}"
        if about.strip():
            entry = _best_match(entries, about)
            if entry is None:
                return f"I don't see that in what I did {label}."
            when = _clock(entry["time"])
            if entry["approval"] == DECLINED:
                return f"No. At {when} you told me not to: {entry['what'].lower()}."
            if entry["approval"] == EXPIRED:
                return f"No. I asked at {when}, but the question ran out before you answered."
            if entry["result"] in ("failed", "not done"):
                return f"I tried at {when}, but it didn't work: {entry['detail'] or entry['what'].lower()}."
            if entry["result"] == "asked you":
                return f"Not yet. At {when} I asked you first and didn't hear a yes."
            after = ", after you said yes" if entry["approval"] == "you said yes" else ""
            return f"Yes, I did, at {when}{after} ({entry['what'][:1].lower()}{entry['what'][1:]})."
        if not entries:
            return f"I didn't do anything for you {label}."
        # The time first: "remind you to stretch at 9:21 AM" was set at 8:51, and must not read as 9:21.
        done = [f"{_clock(e['time'])}, {e['what'][:1].lower()}{e['what'][1:]}" for e in reversed(entries)
                if e["result"] not in ("not done",)][:8]
        skipped = [e for e in entries if e["approval"] == DECLINED]
        text = f"Here's what I did {label}: {'; '.join(done)}." if done else f"I didn't get anything done {label}."
        if skipped:
            text += f" You told me not to {skipped[0]['what'][:1].lower()}{skipped[0]['what'][1:]}."
        if len(entries) > 8:
            text += " The rest is in Settings > Activity."
        return text


explain_tool = ExplainTool()
tool_registry.register_tool(explain_tool)
