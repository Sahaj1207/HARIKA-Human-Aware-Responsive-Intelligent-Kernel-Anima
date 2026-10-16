import asyncio
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools import recent_results
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

# Only files whose default action is "view/edit" are opened; anything that
# would run code (.exe, .bat, .ps1, .py, .lnk, ...) is refused.
OPENABLE_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf",
    ".txt", ".md", ".csv", ".json", ".xml", ".log",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tif", ".tiff",
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm",
    ".zip", ".epub",
}
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "appdata", "$recycle.bin", "site-packages"}
_SCAN_LIMIT = 60000
_SCAN_SECONDS = 4.0


def _known_folder(name: str) -> Optional[Path]:
    """User folders, including ones OneDrive has redirected."""
    home = Path.home()
    for candidate in (home / name, home / "OneDrive" / name):
        if candidate.is_dir():
            return candidate
    return None


class FilesTool(BaseTool):
    """Finds files in the user's personal folders and opens documents/media or folders."""

    FOLDERS = {
        "desktop": "Desktop", "documents": "Documents", "downloads": "Downloads",
        "pictures": "Pictures", "music": "Music", "videos": "Videos",
    }

    manifest = ToolManifest(
        name="files",
        display_name="Files",
        description="Finds files on this computer by name and opens documents, media or personal folders.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "darwin"],
        capabilities=["find_file", "open_file"],
        operations={"find": "find_file", "open": "open_file"},
        free_text_operations=["find", "open"],
        target_aliases={
            "desktop": ["desktop", "desktop folder"],
            "documents": ["documents", "documents folder", "my documents"],
            "downloads": ["downloads", "downloads folder", "my downloads"],
            "pictures": ["pictures", "pictures folder", "photos folder"],
            "music": ["music folder"],
            "videos": ["videos", "videos folder"],
            "screenshots": ["screenshots", "screenshots folder", "harika screenshots"],
        },
        target_description="a file name or a few words from it (e.g. 'resume', 'budget 2024 xlsx'), or a folder such as downloads or documents",
    )
    timeout_seconds = 12.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Reads file names in personal folders", dependencies=[])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not str(args.get("target") or "").strip():
            return False, "Tell me which file or folder you mean."
        return True, None

    def describe_action(self, args: Dict[str, Any]) -> str:
        return f"{args.get('operation') or 'open'} the file '{args.get('target')}'"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        target = str(args["target"]).strip()
        operation = args.get("operation") or "open"

        folder = self._folder(target)
        if folder is not None and operation == "open":
            if dry_run:
                return {"dry_run": True, "action": "open_folder", "path": str(folder)}
            return self._launch(folder, f"Opened your {target} folder.")

        matches = await asyncio.to_thread(self.search, target)
        if not matches:
            return {"action": f"{operation}_file", "query": target, "success": False, "verified": False,
                    "error": f"I couldn't find a file matching '{target}' in your personal folders"}

        if operation == "find":
            recent_results.remember("files", [{"title": m.name, "path": str(m)} for m in matches[:5]])
            listing = "; ".join(f"{i}. {m.name} (in {m.parent.name})" for i, m in enumerate(matches[:5], 1))
            return {"action": "find_file", "query": target, "results": [str(m) for m in matches[:5]],
                    "success": True, "verified": True,
                    "summary": f"I found {len(matches)} matching file{'s' if len(matches) != 1 else ''}: {listing}.", "error": None}

        best = matches[0]
        if dry_run:
            return {"dry_run": True, "action": "open_file", "path": str(best)}
        note = f" ({len(matches)} files matched; this is the most recently changed.)" if len(matches) > 1 else ""
        recent_results.remember("files", [{"title": m.name, "path": str(m)} for m in matches[:5]])
        return self.open_path(best, f"Opened {best.name}.{note}")

    # ------------------------------------------------------------------ search

    def _folder(self, target: str) -> Optional[Path]:
        key, score = self.match_target(target, None)
        if not key or score < 0.9:
            return None
        if key == "screenshots":
            path = Path.home() / "Pictures" / "HARIKA Screenshots"
            return path if path.is_dir() else None
        return _known_folder(self.FOLDERS[key])

    def search_roots(self) -> List[Path]:
        roots = [_known_folder(name) for name in self.FOLDERS.values()]
        onedrive = Path.home() / "OneDrive"
        if onedrive.is_dir():
            roots.append(onedrive)
        return list(dict.fromkeys(r for r in roots if r is not None))

    def search(self, query: str) -> List[Path]:
        words = self._tokens(query)
        if not words:
            return []
        scored: List[Tuple[float, int, float, Path]] = []
        seen, deadline = 0, time.monotonic() + _SCAN_SECONDS
        for root in self.search_roots():
            for directory, subdirs, files in os.walk(root):
                subdirs[:] = [d for d in subdirs if d.lower() not in _SKIP_DIRS and not d.startswith(".")]
                for name in files:
                    seen += 1
                    tokens = self._tokens(name)
                    exact = sum(1 for w in words if w in tokens)
                    partial = sum(1 for w in words if w not in tokens and any(t.startswith(w) for t in tokens))
                    if (exact + partial) / len(words) >= 0.5:
                        path = Path(directory) / name
                        try:
                            modified = path.stat().st_mtime
                        except OSError:
                            continue
                        score = (exact + 0.6 * partial) / len(words)
                        scored.append((score, self._kind_rank(path.suffix), modified, path))
                if seen > _SCAN_LIMIT or time.monotonic() > deadline:
                    break
        # Best word match, then documents before media/other, then most recently changed.
        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return list(dict.fromkeys(item[3] for item in scored))

    @staticmethod
    def _kind_rank(suffix: str) -> int:
        suffix = suffix.lower()
        if suffix in {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".xls", ".xlsx", ".ods", ".csv", ".ppt", ".pptx", ".odp"}:
            return 2
        return 1 if suffix in OPENABLE_EXTENSIONS else 0

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    # ------------------------------------------------------------------ open

    def open_path(self, path: Path, summary: str) -> Dict[str, Any]:
        if path.is_file() and path.suffix.lower() not in OPENABLE_EXTENSIONS:
            return {"action": "open_file", "path": str(path), "success": False, "verified": False,
                    "error": f"{path.name} is a {path.suffix or 'extensionless'} file, and I only open documents, media and folders, never programs or scripts"}
        return self._launch(path, summary)

    @staticmethod
    def _launch(path: Path, summary: str) -> Dict[str, Any]:
        try:
            if platform.system() == "Windows":
                os.startfile(str(path))  # opens with the registered viewer; no shell parsing
            else:
                subprocess.run(["open", str(path)], check=True)
            ok, error = True, None
        except Exception as exc:
            ok, error = False, f"the system couldn't open {path.name}: {exc}"
        return {"action": "open_file", "path": str(path), "success": ok, "verified": ok,
                "summary": summary if ok else None, "error": error}


files_tool = FilesTool()
tool_registry.register_tool(files_tool)
