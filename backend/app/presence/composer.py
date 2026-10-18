"""Says action results in HARIKA's own warm voice, without ever changing a fact.

"Added milk and eggs to your shopping list." -> "Done! Milk and eggs are on your shopping list."

Only short, one-line, successful results are reworded, and only with a cloud brain
(a local CPU model would add seconds). Approval questions, errors, lists, drafts and
briefings are left exactly as they are. Every number, time, name and quoted piece
of the original must survive; otherwise the original is used.
"""
import re
from typing import Optional

_MAX_CHARS = 220
_PROMPT = """You reword one message from HARIKA, a warm personal assistant, so it sounds natural and friendly when said out loud.
Keep every fact, number, time, date, name and quoted text exactly as written. Don't add information, questions, emoji or advice.
Keep it as short as the original or shorter. Output only the reworded message."""


def facts(text: str) -> set:
    """The parts that must survive a rewording: numbers and times, quoted text, and names."""
    found = set(re.findall(r"\d+(?:[.,:]\d+)*\s*(?:%|°|am|pm|AM|PM)?", text))
    found |= set(re.findall(r"[“\"]([^”\"]+)[”\"]", text))
    words = re.findall(r"\b[A-Za-z][\w'-]*\b", text)
    found |= {w for i, w in enumerate(words) if w[0].isupper() and i > 0 and w not in ("I", "OK")}
    return {f.strip() for f in found if f.strip()}


def keeps_facts(original: str, rewrite: str) -> bool:
    lowered = rewrite.lower()
    return all(fact.lower() in lowered for fact in facts(original))


def eligible(text: str) -> bool:
    return bool(text) and len(text) <= _MAX_CHARS and "\n" not in text.strip() and not text.rstrip().endswith("?")


async def compose(text: str, user_message: str, tone: str) -> Optional[str]:
    """A warmer wording of `text`, or None to keep the original."""
    from app.cognition.llm.manager import RoleProvider

    model = RoleProvider("conversation")
    if not eligible(text) or model.is_local():
        return None
    result = await model.generate_response(
        [{"role": "user", "content": f"The user said: {user_message}\nTone: {tone}\nMessage to reword: {text}"}], _PROMPT)
    rewrite = " ".join(str(result.get("response", "")).split()).strip("\"“” ")
    from app.presence.tone import split_tone
    rewrite = split_tone(rewrite)[0]
    if result.get("error") or not rewrite or len(rewrite) > len(text) * 1.6 + 20 or not keeps_facts(text, rewrite):
        return None
    return rewrite
