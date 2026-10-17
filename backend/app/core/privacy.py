"""Settings > Privacy: what HARIKA may look at."""
import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.paths import data_path

DEFAULTS: Dict[str, Any] = {
    # Capture the app you were using when you ask about it (never continuously). With a cloud
    # vision service connected, that picture is sent to it to answer the question.
    "screen_images": True,
}


class PrivacySettings:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("settings", "privacy.json")
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(DEFAULTS)
            try:
                if self.path.exists():
                    data.update({k: v for k, v in json.loads(self.path.read_text(encoding="utf-8")).items() if k in DEFAULTS})
            except (OSError, json.JSONDecodeError):
                pass
            return data

    def update(self, **changes: Any) -> Dict[str, Any]:
        data = {**self.load(), **{k: bool(v) for k, v in changes.items() if k in DEFAULTS and v is not None}}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


privacy_settings = PrivacySettings()
