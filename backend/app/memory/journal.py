"""The conversation journal: what was said and done each day, kept on this computer.

One JSON line per exchange in data/memory/journal/YYYY-MM-DD.jsonl: the time, the
user's words, HARIKA's reply (shortened) and the actions it took. It feeds the
daily digests, "what did we talk about yesterday?" and habit spotting. Kept for
RETENTION_DAYS; can be switched off or wiped in Settings > Memory.
"""
import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.paths import data_path

RETENTION_DAYS = 90
_REPLY_CHARS = 600
_SETTINGS = {"remember_conversations": True, "notice_habits": True}


# Words that say nothing about a topic, so they never make two exchanges look related.
_FILLER = {"the", "and", "for", "you", "your", "that", "this", "what", "did", "was", "were", "are", "about", "with",
           "can", "have", "has", "had", "our", "we", "me", "my", "its", "it's", "from", "into", "then", "there"}


def _words(text: str) -> set:
    found = set()
    for word in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(word) > 2 and word not in _FILLER:
            found.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return found


class Journal:
    def __init__(self, folder: Optional[Path] = None):
        self.folder = folder or data_path("memory", "journal")
        self._lock = threading.Lock()

    # ------------------------------------------------------------- settings

    @property
    def _settings_path(self) -> Path:
        return self.folder.parent / "memory_settings.json"

    def settings(self) -> Dict[str, Any]:
        try:
            stored = json.loads(self._settings_path.read_text(encoding="utf-8")) if self._settings_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            stored = {}
        return {**_SETTINGS, **{k: v for k, v in stored.items() if k in _SETTINGS}}

    def update_settings(self, **changes: Any) -> Dict[str, Any]:
        data = {**self.settings(), **{k: bool(v) for k, v in changes.items() if k in _SETTINGS and v is not None}}
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    # ------------------------------------------------------------- writing

    def record(self, user_id: str, message: str, reply: str, actions: List[Dict[str, Any]],
               when: Optional[datetime] = None) -> bool:
        if not self.settings()["remember_conversations"] or not (message or "").strip():
            return False
        when = when or datetime.now()
        entry = {"time": when.isoformat(timespec="seconds"), "user": user_id, "message": message.strip()[:1000],
                 "reply": (reply or "").strip()[:_REPLY_CHARS], "actions": actions}
        with self._lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            with open(self._file(when.date()), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True

    def prune(self, today: Optional[date] = None) -> int:
        """Removes days older than the retention period; returns how many."""
        cutoff = (today or date.today()) - timedelta(days=RETENTION_DAYS)
        removed = 0
        for day in self.days():
            if day < cutoff:
                self._file(day).unlink(missing_ok=True)
                removed += 1
        return removed

    def wipe(self) -> None:
        with self._lock:
            for day in self.days():
                self._file(day).unlink(missing_ok=True)

    # ------------------------------------------------------------- reading

    def _file(self, day: date) -> Path:
        return self.folder / f"{day.isoformat()}.jsonl"

    def days(self) -> List[date]:
        if not self.folder.exists():
            return []
        found = []
        for path in self.folder.glob("*.jsonl"):
            try:
                found.append(date.fromisoformat(path.stem))
            except ValueError:
                continue
        return sorted(found)

    def entries(self, day: date) -> List[Dict[str, Any]]:
        path = self._file(day)
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def all_entries(self, since: Optional[date] = None) -> List[Dict[str, Any]]:
        return [e for day in self.days() if not since or day >= since for e in self.entries(day)]

    def owner(self) -> str:
        """Whose memories these are: the user of the latest exchange (HARIKA is used by one person)."""
        for day in reversed(self.days()):
            entries = self.entries(day)
            if entries:
                return entries[-1].get("user") or "default"
        return "default"

    def search(self, text: str, limit: int = 12) -> List[Dict[str, Any]]:
        """Exchanges sharing the most words with `text`, best first (ties: most recent)."""
        wanted = _words(text)
        if not wanted:
            return []
        scored = []
        for entry in self.all_entries():
            overlap = len(wanted & _words(f"{entry['message']} {entry['reply']}"))
            if overlap:
                scored.append((overlap, entry["time"], entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in scored[:limit]]


journal = Journal()
