"""Plain-language days ("today", "tomorrow", "sunday", "2026-10-20") as offsets from today."""
from datetime import date, timedelta
from typing import Any, Optional


def day_offset(value: Any, today: date) -> Optional[int]:
    text = str(value or "today").strip().lower()
    if text in ("", "today", "now", "tonight", "this evening", "this morning"):
        return 0
    if text == "tomorrow":
        return 1
    if text.isdigit():
        return int(text)
    try:
        return (date.fromisoformat(text[:10]) - today).days
    except ValueError:
        pass
    for offset in range(7):
        if (today + timedelta(days=offset)).strftime("%A").lower() == text:
            return offset
    return None
