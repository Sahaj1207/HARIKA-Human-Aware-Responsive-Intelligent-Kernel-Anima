"""Where HARIKA keeps its runtime data (memories, reminders, settings, histories).

Development: backend/data inside the repository.
Installed app: the per-user app-data folder the desktop shell passes in
HARIKA_DATA_DIR (e.g. %APPDATA%\\com.harika.desktop on Windows).
"""
import os
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("HARIKA_DATA_DIR")
    return Path(override) if override else Path(__file__).resolve().parents[2] / "data"


def data_path(*parts: str) -> Path:
    return data_dir().joinpath(*parts)
