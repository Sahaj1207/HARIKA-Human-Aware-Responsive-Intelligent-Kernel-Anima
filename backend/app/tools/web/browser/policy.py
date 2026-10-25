"""The rules every website-task step passes before it runs. Decided here, in code, never by the model.

- Sensitive fields (passwords, one-time codes, card and ID numbers) are never typed into:
  the user types those themselves.
- A step that commits something (buys, pays, sends, posts, deletes, books, submits a form
  that changes something) waits for the user's yes. A step counts as committing when the
  model says so, when it submits a form that posts data, or when its button reads like
  one of those (a backstop for when the model doesn't say so).
- Sign-in pages and CAPTCHAs are handed to the user.
- Only http(s) addresses are opened.
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

ACTIONS = {"open", "click", "type", "choose", "scroll", "back", "wait", "done", "ask_user"}
# Labels of buttons that do something that can't simply be undone. A backstop only: the model's
# own "commits" flag and the form's method decide most cases.
_COMMITTING = re.compile(
    r"\b(buy|pay|purchase|place (your )?order|order now|checkout|check out|proceed to (pay|checkout)|confirm|submit|send|"
    r"post|publish|tweet|reply|delete|remove account|unsubscribe|subscribe|book( now)?|reserve|transfer|donate|sign up|"
    r"register|create account|accept)\b", re.I)


@dataclass
class Verdict:
    allowed: bool
    needs_yes: bool = False
    hand_over: str = ""   # why the user has to do this step themselves
    problem: str = ""     # why the step is invalid


def check(step: Dict[str, Any], page: Dict[str, Any]) -> Verdict:
    action = step.get("action")
    if action not in ACTIONS:
        return Verdict(False, problem=f"'{action}' isn't something I can do on a page")
    if action == "open":
        url = str(step.get("url") or "")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return Verdict(False, problem="I can only open web addresses (http or https)")
        return Verdict(True)
    if action in ("scroll", "back", "wait", "done", "ask_user"):
        return Verdict(True)

    element = element_by_id(page, step.get("id"))
    if element is None:
        return Verdict(False, problem="that element isn't on the page any more")
    if element.get("disabled"):
        return Verdict(False, problem=f"“{element.get('label') or 'that'}” is disabled right now")
    if action == "type":
        if element.get("sensitive"):
            return Verdict(False, hand_over=f"“{element.get('label') or 'This field'}” asks for a password, code or "
                                            "card or ID number. Please type it yourself in the window")
        text = str(step.get("text") or "")
        if not text or len(text) > 500:
            return Verdict(False, problem="there's nothing sensible to type")
        if step.get("enter") and element.get("form") == "post":
            return Verdict(True, needs_yes=True)
        return Verdict(True, needs_yes=bool(step.get("commits")))
    if action == "choose":
        if element.get("role") != "select":
            return Verdict(False, problem="choose only works on drop-down lists; click radio buttons and checkboxes")
        if not str(step.get("text") or "").strip():
            return Verdict(False, problem="say which option to choose")
        return Verdict(True, needs_yes=bool(step.get("commits")))
    # click
    committing = bool(step.get("commits")) or (element.get("submits") and element.get("form") == "post") \
        or bool(_COMMITTING.search(element.get("label") or ""))
    return Verdict(True, needs_yes=committing)


def needs_the_user(page: Dict[str, Any]) -> str:
    """Why the user has to step in on this page before the task can go on ('' when they don't)."""
    if page.get("captcha"):
        return "This page wants to check you're human. Please solve it in the window"
    if page.get("password_field"):
        return "This site wants you to sign in. Please sign in yourself in the window"
    return ""


def element_by_id(page: Dict[str, Any], element_id: Any) -> Optional[Dict[str, Any]]:
    try:
        wanted = int(element_id)
    except (TypeError, ValueError):
        return None
    return next((e for e in page.get("elements", []) if e.get("id") == wanted), None)


def describe_step(step: Dict[str, Any], page: Dict[str, Any]) -> str:
    """The step in plain words ("click “Add to cart”"), for progress and approval questions."""
    action = step.get("action")
    element = element_by_id(page, step.get("id")) or {}
    label = element.get("label") or "that"
    if action == "open":
        return f"open {urlparse(str(step.get('url'))).netloc or step.get('url')}"
    if action == "click":
        return f"click “{label}”"
    if action == "type":
        return f"type “{str(step.get('text'))[:60]}” into “{label}”" + (" and press Enter" if step.get("enter") else "")
    if action == "choose":
        return f"choose “{step.get('text')}” in “{label}”"
    if action == "scroll":
        return f"scroll {step.get('direction') or 'down'}"
    return {"back": "go back", "wait": "wait for the page"}.get(action, str(action))
