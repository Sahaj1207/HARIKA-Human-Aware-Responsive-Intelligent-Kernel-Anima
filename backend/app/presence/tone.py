"""The emotional tone of a reply, so HARIKA's voice (and orb) can match what she's saying.

Chat replies carry a tag chosen by the language model ("[empathetic] I'm sorry...");
it is removed before anyone sees the text. Results of actions get a tone from what
happened. Questions that ask for approval are always plain, so a serious decision is
never dressed up.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

TONES = ("warm", "cheerful", "excited", "playful", "empathetic", "calm", "apologetic", "serious", "neutral")
DEFAULT = "warm"

_TAG = re.compile(r"^\s*[\[(]\s*(?:tone\s*[:=]\s*)?([a-z]+)\s*[\])]\s*[:\-–]?\s*", re.I)


def split_tone(text: str) -> Tuple[str, Optional[str]]:
    """'[empathetic] I'm so sorry.' -> ("I'm so sorry.", "empathetic"). Unknown tags are left in the text."""
    match = _TAG.match(text or "")
    if not match or match.group(1).lower() not in TONES:
        return text or "", None
    return text[match.end():].lstrip(), match.group(1).lower()


def strip_tags(text: str) -> Tuple[str, Optional[str]]:
    """Removes a tone tag at the start of each paragraph; returns the first one found."""
    found: Optional[str] = None
    parts = []
    for paragraph in (text or "").split("\n\n"):
        cleaned, tone = split_tone(paragraph)
        found = found or tone
        parts.append(cleaned)
    return "\n\n".join(parts), found


def tone_for(results: List[Any], chat_tone: Optional[str], asking: bool = False) -> str:
    """One tone for the whole reply."""
    if asking:
        return "neutral"
    if chat_tone:
        return chat_tone
    outcomes = [r.get("result", r) for r in results if isinstance(r, dict)]
    explicit = next((o.get("tone") for o in outcomes if isinstance(o, dict) and o.get("tone") in TONES), None)
    if explicit:
        return explicit
    if any(isinstance(o, dict) and (o.get("success") is False or o.get("status") in ("failed", "error")) for o in outcomes):
        return "apologetic"
    return DEFAULT


CHAT_TONE_INSTRUCTION = (
    "- Start every reply with one tone tag in square brackets that fits how you are speaking, chosen from: "
    + ", ".join(f"[{t}]" for t in TONES if t != "neutral")
    + ". Example: \"[empathetic] That sounds exhausting. Want me to clear your evening?\" The tag is removed before "
    "the user sees it and sets your voice."
)
