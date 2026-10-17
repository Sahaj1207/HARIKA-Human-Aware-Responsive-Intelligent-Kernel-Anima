"""Notes and lists: "take a note ...", "add milk to my shopping list", "what's on my to-do list?".

Kept on this computer. Any list name works ("shopping", "packing", "gift ideas"); a
new list is made the first time something is added to it. Clearing a whole list
waits for the user's yes.
"""
import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.paths import data_path
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

_DEFAULT_LIST = "to-do"
_NOTES = "notes"
_CLEAR_TTL = 600


def list_key(name: str) -> str:
    """'my Shopping List' -> 'shopping'; 'todo'/'to do' -> 'to-do'; 'notes' stays 'notes'."""
    words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in ("my", "the", "list", "a")]
    key = " ".join(words)
    if key in ("", "todo", "to do", "todos", "to dos", "tasks", "task"):
        return _DEFAULT_LIST
    if key in ("note", "notes"):
        return _NOTES
    return key


def _same(a: str, b: str) -> bool:
    return " ".join(re.findall(r"[a-z0-9]+", a.lower())) == " ".join(re.findall(r"[a-z0-9]+", b.lower()))


class NotesStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("notes", "notes.json")
        self._lock = threading.Lock()

    def load(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            except (OSError, json.JSONDecodeError):
                return {}

    def _save(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(self, key: str, texts: List[str]) -> List[str]:
        """Adds what isn't already on the list (open items); returns what was added."""
        data = self.load()
        items = data.setdefault(key, [])
        added = []
        for text in texts:
            if key != _NOTES and any(_same(i["text"], text) and not i.get("done") for i in items):
                continue
            items.append({"id": uuid.uuid4().hex[:8], "text": text, "done": False,
                          "added": datetime.now().isoformat(timespec="seconds")})
            added.append(text)
        self._save(data)
        return added

    def items(self, key: str, include_done: bool = False) -> List[Dict[str, Any]]:
        return [i for i in self.load().get(key, []) if include_done or not i.get("done")]

    def check_off(self, key: str, words: str) -> List[str]:
        """Marks matching open items done ("milk" ticks "2 litres of milk")."""
        data = self.load()
        wanted = set(re.findall(r"[a-z0-9]+", words.lower()))
        done = []
        for item in data.get(key, []):
            if not item.get("done") and wanted and wanted <= set(re.findall(r"[a-z0-9]+", item["text"].lower())):
                item["done"] = True
                done.append(item["text"])
        self._save(data)
        return done

    def clear(self, key: str) -> int:
        data = self.load()
        count = len(data.pop(key, []))
        self._save(data)
        return count

    def names(self) -> List[str]:
        return [k for k, v in self.load().items() if any(not i.get("done") for i in v)]


notes_store = NotesStore()


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" and {items[-1]}"


def _title(key: str) -> str:
    return "your notes" if key == _NOTES else f"your {key} list"


class NotesTool(BaseTool):
    manifest = ToolManifest(
        name="notes",
        display_name="Notes & lists",
        description="Takes notes and keeps lists (to-do, shopping or any other), reads them back and ticks items off.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["take_note", "add_to_list", "show_list", "check_off", "clear_list", "remove_list"],
        operations={"note": "take_note", "add_to_list": "add_to_list", "show_list": "show_list",
                    "check_off": "check_off", "clear_list": "clear_list"},
        free_text_operations=["note", "add_to_list", "show_list", "check_off", "clear_list"],
        default_targets={"show_list": "to-do"},
        operation_permissions={"remove_list": PermissionLevel.HIGH},
        ability="take notes and keep your to-do, shopping and other lists",
        target_description=(
            "for note: the note's text; for add_to_list and check_off: the item, with parameters.list naming the "
            "list ('shopping', 'to-do', or any other; default to-do) and parameters.items for several items; "
            "for show_list and clear_list: the list's name ('shopping', 'to-do', 'notes')"
        ),
    )
    timeout_seconds = 5.0

    def __init__(self, store: NotesStore = notes_store):
        self.store = store
        self.pending_clear: Optional[Tuple[str, float]] = None

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Notes stored on this computer", dependencies=[])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        if operation == "show_list":
            return text or _DEFAULT_LIST, 0.8
        return (text, 0.7) if text else (None, 0.0)

    def describe_action(self, args: Dict[str, Any]) -> str:
        operation, target = args.get("operation"), str(args.get("target") or "").strip()
        key = list_key(str(args.get("list") or ""))
        if operation == "note":
            return "take a note"
        if operation == "add_to_list":
            return f"add {target} to {_title(key)}"
        if operation == "show_list":
            return f"read {_title(list_key(target))}"
        if operation == "check_off":
            return f"tick off {target}"
        if operation in ("clear_list", "remove_list"):
            return f"clear {_title(list_key(target))}"
        return super().describe_action(args)

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation = args.get("operation")
        if dry_run:
            return {"dry_run": True, "action": operation, "target": args.get("target")}
        target = str(args.get("target") or "").strip().strip("\"“”")
        if operation == "note":
            if not target:
                return self._fail("What should the note say?")
            self.store.add(_NOTES, [target])
            return self._ok("take_note", f"Noted: {target}")
        if operation == "add_to_list":
            return self._add(args, target)
        if operation == "show_list":
            return self._show(list_key(target))
        if operation == "check_off":
            key = list_key(str(args.get("list") or "")) if args.get("list") else self._list_holding(target)
            done = self.store.check_off(key, target)
            if not done:
                return self._fail(f"I couldn't find {target} on {_title(key)}")
            return self._ok("check_off", f"Ticked off {_join(done)}.")
        if operation == "clear_list":
            key = list_key(target)
            count = len(self.store.items(key))
            if not count:
                return self._fail(f"{_title(key).capitalize()} is already empty")
            self.pending_clear = (key, time.time())
            question = f"Clear {_title(key)} ({count} item{'s' if count != 1 else ''})?"
            return {**self._ok("clear_list", question),
                    "confirmation": {"capability": "remove_list", "operation": "remove_list", "target": key, "question": question}}
        if operation == "remove_list":
            if self.pending_clear is None or time.time() - self.pending_clear[1] > _CLEAR_TTL:
                return self._fail("there's no list waiting to be cleared")
            key, self.pending_clear = self.pending_clear[0], None
            self.store.clear(key)
            return self._ok("remove_list", f"Cleared {_title(key)}.")
        return self._fail(f"I can't do '{operation}' with notes")

    def _add(self, args, target: str) -> Dict[str, Any]:
        key = list_key(str(args.get("list") or _DEFAULT_LIST))
        raw = args.get("items") if isinstance(args.get("items"), list) and args.get("items") else [target]
        items = [str(i).strip().strip("\"“”") for i in raw if str(i).strip()]
        if not items:
            return self._fail("What should I add?")
        added = self.store.add(key, items)
        already = [i for i in items if i not in added]
        if not added:
            return self._ok("add_to_list", f"{_join(already).capitalize()} {'is' if len(already) == 1 else 'are'} already on {_title(key)}.")
        summary = f"Added {_join(added)} to {_title(key)}."
        if already:
            summary += f" ({_join(already)} {'was' if len(already) == 1 else 'were'} already there.)"
        return self._ok("add_to_list", summary)

    def _show(self, key: str) -> Dict[str, Any]:
        items = self.store.items(key)
        if not items:
            others = [n for n in self.store.names() if n != key]
            hint = f" You have: {', '.join(_title(n) for n in others)}." if others else ""
            empty = "You don't have any notes." if key == _NOTES else f"{_title(key).capitalize()} is empty."
            return self._ok("show_list", f"{empty}{hint}")
        lines = "\n".join(f"{i}. {item['text']}" for i, item in enumerate(items, 1))
        return self._ok("show_list", f"{_title(key).capitalize()}:\n{lines}")

    def _list_holding(self, words: str) -> str:
        """Which list has this item, when the user didn't say ("tick off milk")."""
        wanted = set(re.findall(r"[a-z0-9]+", words.lower()))
        for key in self.store.names():
            if any(wanted and wanted <= set(re.findall(r"[a-z0-9]+", i["text"].lower())) for i in self.store.items(key)):
                return key
        return _DEFAULT_LIST

    @staticmethod
    def _ok(action: str, summary: str) -> Dict[str, Any]:
        return {"action": action, "success": True, "verified": True, "summary": summary, "error": None}

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


notes_tool = NotesTool()
tool_registry.register_tool(notes_tool)
