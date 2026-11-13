"""Where a reply came from, so HARIKA can answer "how did you know that?" and "did that go online?".

While a request is handled, each part notes itself here: the abilities that ran (and what each
reads and where it sends data, from their manifests), every language-model answer (which service,
and whether it was a backup) and whether remembered facts about the user were used. The router
keeps the last few replies' notes in memory only; nothing is written to disk.

Noting must never get in the way of answering: every function here is safe to call anywhere,
and does nothing outside a request.
"""
from collections import deque
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

_current: ContextVar[Optional[Dict[str, Any]]] = ContextVar("harika_provenance", default=None)
KEPT = 5
recent: Deque[Dict[str, Any]] = deque(maxlen=KEPT)  # the last few replies, newest last


def start() -> None:
    """A new request: notes from here on belong to it (each request runs in its own context)."""
    _current.set({"abilities": [], "ai": [], "memories": False})


def note_ai(role: str, service: str, backup_for: str = "") -> None:
    notes = _current.get()
    if notes is not None:
        notes["ai"].append({"role": role, "service": service, "backup_for": backup_for})


def note_memories() -> None:
    notes = _current.get()
    if notes is not None:
        notes["memories"] = True


def note_ability(name: str, uses: str, sends_to: str) -> None:
    notes = _current.get()
    if notes is not None and all(a["name"] != name for a in notes["abilities"]):
        notes["abilities"].append({"name": name, "uses": uses, "sends_to": sends_to})


def skip() -> None:
    """This reply is HARIKA explaining an earlier one: don't keep it, so "and did that go online?"
    still means the reply before."""
    notes = _current.get()
    if notes is not None:
        notes["skip"] = True


def finish(message: str, reply: str) -> None:
    """Keeps this request's notes with its reply (only replies that said something)."""
    notes = _current.get()
    if notes is not None and (reply or "").strip() and not notes.get("skip"):
        recent.append({**notes, "message": message, "reply": reply.strip()[:300],
                       "time": datetime.now().isoformat(timespec="seconds")})


def last_reply() -> Optional[Dict[str, Any]]:
    return recent[-1] if recent else None
