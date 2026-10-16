"""Read-only index of applications the OS reports as launchable.

The index is the source of truth for "open <any installed app>": a request is
matched against names the OS itself registered, and launching uses the OS
application ID from that index, never text supplied by the user or an LLM.
"""
import json
import logging
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("harika.tools.installed_apps")


@dataclass(frozen=True)
class InstalledApp:
    name: str
    app_id: str

    @property
    def process_candidates(self) -> List[str]:
        """Likely executable names, used only to verify a launch/close."""
        words = re.findall(r"[a-z0-9]+", self.name.lower())
        candidates = list(words) + ["".join(words)]
        tail = self.app_id.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if tail.endswith(".exe"):
            candidates.insert(0, tail[:-4])
        return [c for c in dict.fromkeys(candidates) if len(c) > 1]


class InstalledAppIndex:
    REFRESH_SECONDS = 300.0

    def __init__(self):
        self._apps: Dict[str, InstalledApp] = {}
        self._loaded_at = 0.0
        self._lock = threading.Lock()

    def _load(self) -> None:
        if platform.system().lower() != "windows":
            return
        try:
            # Fixed command with no user input; Get-StartApps lists desktop and Store apps.
            out = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            rows = json.loads(out.stdout or "[]")
            if isinstance(rows, dict):
                rows = [rows]
            apps = {}
            for row in rows:
                name, app_id = (row.get("Name") or "").strip(), (row.get("AppID") or "").strip()
                if name and app_id:
                    apps.setdefault(self.normalize(name), InstalledApp(name=name, app_id=app_id))
            self._apps = apps
            logger.info(f"[InstalledAppIndex] Indexed {len(apps)} launchable applications.")
        except Exception as exc:
            logger.warning(f"[InstalledAppIndex] Could not index installed apps: {exc}")
        finally:
            self._loaded_at = time.time()

    def apps(self) -> Dict[str, InstalledApp]:
        with self._lock:
            if not self._loaded_at or time.time() - self._loaded_at > self.REFRESH_SECONDS:
                self._load()
            return self._apps

    def find(self, requested: str) -> Optional[InstalledApp]:
        """Exact name match first, then a unique name that contains every requested word."""
        query = self.normalize(requested)
        if not query:
            return None
        apps = self.apps()
        if query in apps:
            return apps[query]
        words = query.split()
        matches = [app for key, app in apps.items() if all(w in key.split() for w in words)]
        if len(matches) == 1:
            return matches[0]
        # Prefer the shortest name when several contain the words ("spotify" vs "spotify widget").
        if matches:
            matches.sort(key=lambda app: len(app.name))
            if len(matches[0].name.split()) == len(words):
                return matches[0]
        return None

    @staticmethod
    def normalize(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9+#]+", (value or "").lower()))


installed_app_index = InstalledAppIndex()
