"""Follow-through: "I'll call the bank on Monday" -> "Want me to remind you Monday at 9 AM?".

The chat model marks a plan the user states for themselves with a hidden note at the
end of its reply. HARIKA then offers a reminder; the offer is held like any approval
and only the user's yes creates it.
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

OFFER_INSTRUCTION = (
    "- When the user says they themselves will do something at a particular future day or time (\"I'll call the "
    "bank on Monday\", \"I need to submit the form by Friday\") and did not ask for a reminder, end your reply with "
    "a separate line \"[offer_reminder: <the task, as a short phrase> | <YYYY-MM-DDTHH:MM local time; 09:00 if no time "
    "was said>]\". At most one, never for things already done or other people's plans. The line is hidden from the "
    "user, who is then asked if they want the reminder, so don't ask it yourself."
)
_OFFER = re.compile(r"\[\s*offer_reminder\s*:\s*([^\]|\n]{2,160})\|\s*([0-9T:\- ]{10,19})\s*\]", re.I)
_LONGEST = timedelta(days=90)


def split_offer(text: str, now: Optional[datetime] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Removes offer notes from a reply; returns the reply and a valid offer (or None)."""
    now = now or datetime.now()
    offer = None
    for task, when in _OFFER.findall(text or ""):
        try:
            due = datetime.fromisoformat(when.strip().replace(" ", "T"))
        except ValueError:
            continue
        if now < due <= now + _LONGEST and task.strip():
            offer = {"task": task.strip().rstrip("."), "at": due.isoformat(timespec="minutes")}
            break
    return _OFFER.sub("", text or "").strip(), offer


def as_follow_up(offer: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """The question to add to the reply, and the held reminder it would create."""
    from app.tools.system.reminders import _spoken_time

    due = datetime.fromisoformat(offer["at"])
    question = f"Want me to remind you {_spoken_time(due)}?"
    return question, {"capability": "create_reminder", "operation": "remind", "target": offer["task"],
                      "parameters": {"at": offer["at"]}, "question": question}
