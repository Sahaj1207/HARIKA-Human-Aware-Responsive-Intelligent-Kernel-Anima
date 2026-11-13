"""What HARIKA did: one line per action, for Settings > Activity.

Each entry says what happened in plain words, why (the user asked, said yes, a routine or a
reminder), whether it needed the user's approval and what they said, and how it went. It
never holds the conversation itself, so it can stay on when "Remember our conversations" is
off. Kept on this computer for KEEP_DAYS days; can be switched off and cleared in Settings.

Recording must never get in the way of HARIKA answering: every write swallows its own errors.
"""
import json
import logging
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.paths import data_path

logger = logging.getLogger("harika.memory.activity")

KEEP_DAYS = 30

# why
ASKED = "you asked"
SAID_YES = "you said yes"
ROUTINE = "routine"
REMINDER = "reminder"
# approval
NOT_NEEDED = "not needed"
APPROVED = "you said yes"
DECLINED = "you said no"
EXPIRED = "the question expired"
WAITING = "waiting for your yes"
HANDED_OVER = "handed to you"
# result
DONE = "done"
UNCONFIRMED = "done, but I couldn't confirm it"
FAILED = "failed"
NOT_DONE = "not done"
ASKED_YOU = "asked you"


class ActivityLog:
    def __init__(self, folder: Optional[Path] = None, settings_path: Optional[Path] = None):
        self.folder = folder or data_path("activity")
        self.settings_path = settings_path or data_path("settings", "activity.json")
        self._lock = threading.Lock()

    def keeping(self) -> bool:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8")).get("keep", True) is not False
        except (OSError, ValueError):
            return True

    def set_keeping(self, keep: bool) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps({"keep": bool(keep)}), encoding="utf-8")

    def add(self, what: str, why: str = ASKED, approval: str = NOT_NEEDED, result: str = DONE, detail: str = "",
            when: Optional[datetime] = None) -> None:
        """Notes one action. Never raises: a full disk mustn't stop HARIKA answering."""
        try:
            if not self.keeping() or not (what or "").strip():
                return
            when = when or datetime.now()
            entry = {"time": when.isoformat(timespec="seconds"), "what": _sentence(what)[:200], "why": why,
                     "approval": approval, "result": result, "detail": (detail or "").strip()[:300]}
            with self._lock:
                self.folder.mkdir(parents=True, exist_ok=True)
                with open(self.folder / f"{when.date().isoformat()}.jsonl", "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.info(f"[Activity] Not recorded: {exc}")

    def entries(self, days: int = 7, needed_approval: bool = False) -> List[Dict[str, Any]]:
        """Newest first, from the last `days` days."""
        out: List[Dict[str, Any]] = []
        today = date.today()
        for back in range(days):
            path = self.folder / f"{(today - timedelta(days=back)).isoformat()}.jsonl"
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not needed_approval or entry.get("approval") not in (NOT_NEEDED, None):
                    out.append(entry)
        return out

    def clear(self) -> None:
        with self._lock:
            for path in self.folder.glob("*.jsonl") if self.folder.exists() else []:
                path.unlink(missing_ok=True)

    def prune(self, today: Optional[date] = None) -> None:
        cutoff = (today or date.today()) - timedelta(days=KEEP_DAYS)
        for path in self.folder.glob("*.jsonl") if self.folder.exists() else []:
            try:
                if date.fromisoformat(path.stem) < cutoff:
                    path.unlink(missing_ok=True)
            except ValueError:
                continue


def _sentence(text: str) -> str:
    text = " ".join(str(text).split())
    return text[:1].upper() + text[1:]


activity_log = ActivityLog()
