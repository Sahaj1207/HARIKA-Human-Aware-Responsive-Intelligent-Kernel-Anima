"""Plain-language days ("today", "tomorrow", "next monday", "2026-10-20") as offsets from today."""
import re
from datetime import date, timedelta
from typing import Any, Optional


def day_offset(value: Any, today: date) -> Optional[int]:
    text = re.sub(r"\s+", " ", str(value or "today").strip().lower())
    text = re.sub(r"^(on|for|this coming|this|coming)\s+", "", text)
    upcoming = text.startswith("next ")
    text = text[5:] if upcoming else text
    if text in ("", "today", "now", "tonight", "this evening", "this morning"):
        return 0
    if text in ("tomorrow", "day after today"):
        return 1
    if text == "day after tomorrow":
        return 2
    if text == "week":
        return 7 if upcoming else 0
    if text.isdigit():
        return int(text)
    try:
        return (date.fromisoformat(text[:10]) - today).days
    except ValueError:
        pass
    # A weekday means its next occurrence; "next <today's weekday>" is a week away.
    for offset in range(1 if upcoming else 0, 8):
        if (today + timedelta(days=offset)).strftime("%A").lower() == text:
            return offset
    return None
