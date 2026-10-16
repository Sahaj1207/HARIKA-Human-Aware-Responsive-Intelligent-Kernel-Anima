"""Settings > General > Daily: home city for weather, and the morning briefing."""
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.paths import data_path

logger = logging.getLogger("harika.daily")

DEFAULTS: Dict[str, Any] = {
    "home": "",                 # city for weather; "" means use the computer's approximate location
    "briefing_enabled": False,  # say good morning with the day's briefing
    "briefing_time": "08:00",   # 24-hour local time
    "last_briefing": "",        # date of the last scheduled briefing, so it happens once a day
}


class DailySettings:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("settings", "daily.json")
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(DEFAULTS)
            if self.path.exists():
                try:
                    stored = json.loads(self.path.read_text(encoding="utf-8"))
                    data.update({k: v for k, v in stored.items() if k in DEFAULTS})
                except (OSError, json.JSONDecodeError):
                    logger.warning("[Daily] Settings unreadable; using defaults.")
            return data

    def update(self, **changes: Any) -> Dict[str, Any]:
        changes = {k: v for k, v in changes.items() if k in DEFAULTS and v is not None}
        if "briefing_time" in changes and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(changes["briefing_time"])):
            raise ValueError("briefing_time must be HH:MM (24-hour).")
        if "home" in changes:
            changes["home"] = str(changes["home"]).strip()[:80]
        data = self.load()
        data.update(changes)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


daily_settings = DailySettings()
