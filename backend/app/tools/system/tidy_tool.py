"""Tidying up: "clean up my downloads", "get rid of old installers on my desktop".

Looks through Downloads or Desktop (nowhere else) for files that are usually safe to
clear: installers, duplicate copies, zips already extracted next to themselves, and
big files untouched for months. It reports what it found and asks; only a yes moves
them, and only to the Recycle Bin, so everything can be restored.
"""
import ctypes
import hashlib
import os
import platform
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

KINDS = ("installers", "duplicates", "extracted", "large")
_INSTALLERS = {".exe", ".msi", ".msix", ".appx", ".dmg", ".pkg"}
_ARCHIVES = {".zip", ".rar", ".7z", ".tar", ".gz"}
_INSTALLER_AGE = 7 * 86400       # a fresh installer may still be needed
_LARGE_BYTES = 200 * 1024 * 1024
_LARGE_AGE = 90 * 86400
_MAX_DEPTH = 2
_PENDING_TTL = 600
_LABELS = {"installers": "installer", "duplicates": "duplicate copy", "extracted": "already-extracted zip",
           "large": "big file untouched for 3 months"}


def _size(n: float) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _plural(count: int, label: str) -> str:
    if count == 1:
        return f"1 {label}"
    first, _, rest = label.partition(" ")
    first = first[:-1] + "ies" if first.endswith("y") else first + "s"
    return f"{count} {first}{(' ' + rest) if rest else ''}"


def _files(folder: Path) -> List[Path]:
    out: List[Path] = []
    base = len(folder.parts)
    for directory, subdirs, names in os.walk(folder):
        if len(Path(directory).parts) - base >= _MAX_DEPTH:
            subdirs[:] = []
        subdirs[:] = [d for d in subdirs if not d.startswith(".")]
        out += [Path(directory) / n for n in names if not n.startswith(".") and not n.lower().endswith((".tmp", ".crdownload", ".part"))]
    return out


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def find_clutter(folder: Path, kinds=KINDS, now: Optional[float] = None) -> Dict[str, List[Path]]:
    now = now or time.time()
    found: Dict[str, List[Path]] = {kind: [] for kind in KINDS}
    files = _files(folder)
    stats = {}
    for path in files:
        try:
            stats[path] = path.stat()
        except OSError:
            continue
    by_size: Dict[int, List[Path]] = defaultdict(list)
    for path, st in stats.items():
        suffix = path.suffix.lower()
        if "installers" in kinds and suffix in _INSTALLERS and now - st.st_mtime > _INSTALLER_AGE:
            found["installers"].append(path)
        elif "extracted" in kinds and suffix in _ARCHIVES and (path.parent / path.stem).is_dir():
            found["extracted"].append(path)
        elif "large" in kinds and st.st_size >= _LARGE_BYTES and now - st.st_mtime > _LARGE_AGE:
            found["large"].append(path)
        if st.st_size > 0:
            by_size[st.st_size].append(path)
    if "duplicates" in kinds:
        taken = {p for paths in found.values() for p in paths}
        for size, paths in by_size.items():
            if len(paths) < 2:
                continue
            by_hash: Dict[str, List[Path]] = defaultdict(list)
            for path in paths:
                try:
                    by_hash[_digest(path)].append(path)
                except OSError:
                    continue
            for copies in by_hash.values():
                # The oldest is the original ("report.pdf"); later ones ("report (1).pdf") are copies.
                copies.sort(key=lambda p: (stats[p].st_mtime, len(p.name)))
                found["duplicates"] += [p for p in copies[1:] if p not in taken]
    return {kind: sorted(paths) for kind, paths in found.items() if paths}


def to_recycle_bin(paths: List[Path]) -> int:
    """Moves files to the Recycle Bin (they can be restored). Returns how many were moved."""
    if platform.system() != "Windows" or not paths:
        return 0

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p),
                    ("pTo", ctypes.c_wchar_p), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]

    FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT, FOF_NOERRORUI = 3, 0x40, 0x10, 0x4, 0x400
    existing = [p for p in paths if p.is_file()]
    if not existing:
        return 0
    operation = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom="\0".join(str(p) for p in existing) + "\0\0",
                                fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI)
    ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    return sum(1 for p in existing if not p.exists())


class TidyTool(BaseTool):
    manifest = ToolManifest(
        name="tidy",
        display_name="Tidy up",
        description="Finds clutter in Downloads or Desktop (old installers, duplicate copies, extracted zips, big old files) and moves it to the Recycle Bin after you say yes.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows"],
        capabilities=["suggest_cleanup", "recycle_clutter"],
        operations={"tidy": "suggest_cleanup"},
        default_targets={"tidy": "downloads"},
        operation_permissions={"recycle_clutter": PermissionLevel.HIGH},
        ability="tidy up your Downloads or Desktop (old installers, duplicates and more), with your yes",
        target_description=(
            "'downloads' or 'desktop'; parameters.kinds optionally limits it to some of: installers, duplicates, "
            "extracted (zips already unpacked), large (big files untouched for months)"
        ),
    )
    timeout_seconds = 60.0

    def __init__(self):
        self.pending: Optional[Tuple[List[Path], float]] = None

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=platform.system() == "Windows", reason="Downloads and Desktop", dependencies=[])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").lower()
        return ("desktop", 0.9) if "desktop" in text else ("downloads", 0.8)

    def describe_action(self, args: Dict[str, Any]) -> str:
        if args.get("operation") == "recycle_clutter":
            return "move those files to the Recycle Bin"
        return f"look for clutter in your {args.get('target') or 'downloads'}"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        import asyncio
        if args.get("operation") == "recycle_clutter":
            return await asyncio.to_thread(self._recycle, dry_run)
        from app.tools.system.files import _known_folder

        where = "desktop" if str(args.get("target") or "").lower() == "desktop" else "downloads"
        folder = _known_folder(where.capitalize())
        if folder is None:
            return {"success": False, "verified": False, "error": f"I couldn't find your {where.capitalize()} folder"}
        raw = args.get("kinds") or []
        kinds = [k for k in ([raw] if isinstance(raw, str) else raw) if k in KINDS]
        found = await asyncio.to_thread(find_clutter, folder, kinds or KINDS)
        if dry_run:
            return {"dry_run": True, "action": "suggest_cleanup", "found": {k: len(v) for k, v in found.items()}}
        if not found:
            return {"action": "suggest_cleanup", "success": True, "verified": True,
                    "summary": f"Your {where.capitalize()} folder looks tidy. Nothing I'd clear out.", "error": None}
        files = [p for paths in found.values() for p in paths]
        total = sum(p.stat().st_size for p in files if p.exists())
        parts = [f"{_plural(len(found[k]), _LABELS[k])}" for k in KINDS if k in found]
        examples = ", ".join(p.name for p in files[:4]) + (f" and {len(files) - 4} more" if len(files) > 4 else "")
        question = f"Move {'it' if len(files) == 1 else f'these {len(files)} files'} to the Recycle Bin?"
        self.pending = (files, time.time())
        summary = (f"In your {where.capitalize()} folder you could free {_size(total)}: {', '.join(parts)} "
                   f"({examples}). {question} You can restore anything from there.")
        return {"action": "suggest_cleanup", "success": True, "verified": True, "summary": summary, "error": None,
                "files": [str(p) for p in files],
                "confirmation": {"capability": "recycle_clutter", "operation": "recycle_clutter", "target": where,
                                 "question": question}}

    def _recycle(self, dry_run: bool) -> Dict[str, Any]:
        if self.pending is None or time.time() - self.pending[1] > _PENDING_TTL:
            return {"success": False, "verified": False, "error": "there's nothing waiting to be cleared; ask me to look again"}
        files = self.pending[0]
        if dry_run:
            return {"dry_run": True, "action": "recycle_clutter", "count": len(files)}
        self.pending = None
        moved = to_recycle_bin(files)
        if moved == 0:
            return {"success": False, "verified": False, "error": "Windows didn't move the files; they may be open in another app"}
        left = len([p for p in files if p.exists()])
        note = f" {left} couldn't be moved (they may be open)." if left else ""
        return {"action": "recycle_clutter", "success": True, "verified": True,
                "summary": f"Moved {moved} file{'s' if moved != 1 else ''} to the Recycle Bin.{note}", "error": None}


tidy_tool = TidyTool()
tool_registry.register_tool(tidy_tool)
