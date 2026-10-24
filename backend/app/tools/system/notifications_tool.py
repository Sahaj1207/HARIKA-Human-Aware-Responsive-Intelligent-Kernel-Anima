"""Notifications: "any new messages on my phone?", "what did Mom text?", "what notifications did I get?".

Reads the notifications Windows is holding in the notification centre (the official
UserNotificationListener API, read-only). A phone linked with Phone Link shows its
notifications there too, which is how HARIKA sees messages on the phone. The list is
built straight from what Windows returns; nothing is generated or sent anywhere.
"""
import asyncio
import logging
import platform
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

logger = logging.getLogger("harika.tools.notifications")

PHONE = "phone"
ALL = "all"
_PHONE_APP = "microsoft.yourphone"  # Phone Link's app id
_SHOWN = 8
_ACCESS_HELP = ("Windows isn't letting me read notifications. Turn it on in Windows Settings > Privacy & security > "
                "Notifications > \"Let apps access your notifications\"")


class Notice:
    def __init__(self, app: str, app_id: str, lines: List[str], when: datetime):
        self.app, self.app_id, self.lines, self.when = app, app_id, lines, when

    @property
    def from_phone(self) -> bool:
        return self.app_id.lower().startswith(_PHONE_APP)

    def matches(self, words: List[str]) -> bool:
        text = " ".join([self.app, *self.lines]).lower()
        return all(re.search(rf"\b{re.escape(w)}", text) for w in words)

    def describe(self, now: datetime) -> str:
        title, body = (self.lines + ["", ""])[:2]
        source = "" if self.from_phone else f"{self.app}: "
        text = f"{title}: {body}" if title and body else (title or body or "(no text)")
        return f"{source}{text[:200]} ({_ago(self.when, now)})"


def _ago(when: datetime, now: datetime) -> str:
    minutes = int((now - when).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 24 * 60:
        return f"{minutes // 60} h ago"
    return when.astimezone().strftime("%a %d %b")


async def read_notices() -> Tuple[Optional[List[Notice]], str]:
    """(notices, "") or (None, why not)."""
    if platform.system() != "Windows":
        return None, "Reading notifications works on Windows only"
    from app.core.native import load_in_safe_order
    load_in_safe_order()  # WinRT loaded before onnxruntime crashes the process
    try:
        from winrt.windows.ui.notifications import NotificationKinds
        from winrt.windows.ui.notifications.management import UserNotificationListener
    except ImportError:
        return None, "Reading notifications isn't available in this version of HARIKA"
    listener = UserNotificationListener.current
    status = int(listener.get_access_status())
    if status == 0:  # never asked: Windows decides (desktop apps are usually allowed)
        status = int(await listener.request_access_async())
    if status != 1:
        return None, _ACCESS_HELP
    notices = []
    for item in await listener.get_notifications_async(NotificationKinds.TOAST):
        try:
            info = item.app_info
            app, app_id = info.display_info.display_name, info.app_user_model_id
        except Exception:
            app, app_id = "An app", ""
        try:
            binding = item.notification.visual.get_binding("ToastGeneric")
            lines = [t.text.strip() for t in binding.get_text_elements() if t.text and t.text.strip()] if binding else []
        except Exception:
            lines = []
        notices.append(Notice(app, app_id, lines, item.creation_time))
    notices.sort(key=lambda n: n.when, reverse=True)
    return notices, ""


class NotificationsTool(BaseTool):
    manifest = ToolManifest(
        name="notifications",
        display_name="Notifications",
        description="Reads your recent notifications, including your phone's messages when it's linked with Phone Link.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="system",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows"],
        capabilities=["read_notifications"],
        operations={"notifications": "read_notifications"},
        free_text_operations=["notifications"],
        default_targets={"notifications": "all"},
        ability="read your notifications, and your phone's messages when it's linked with Phone Link",
        target_description=(
            "'phone' for the phone's notifications (messages, calls, apps on the phone), 'all' for everything, or "
            "who or which app they're from ('Mom', 'WhatsApp'); parameters.phone true when it's about the phone"
        ),
    )
    timeout_seconds = 15.0

    def __init__(self, reader=read_notices):
        self.reader = reader

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=platform.system() == "Windows", reason="Windows notification centre", dependencies=["winrt"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        return ((requested or "").strip() or ALL), 0.8

    def describe_action(self, args: Dict[str, Any]) -> str:
        return "check your notifications"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return {"dry_run": True, "action": "read_notifications"}
        notices, problem = await self.reader()
        if notices is None:
            return {"success": False, "verified": False, "error": problem}
        asked = str(args.get("target") or ALL).strip()
        target = asked.lower()
        phone_only = target == PHONE or str(args.get("phone")).lower() == "true"
        words = [] if target in (PHONE, ALL) else re.findall(r"[a-z0-9]+", target)
        chosen = [n for n in notices if (not phone_only or n.from_phone) and (not words or n.matches(words))]
        where = "on your phone" if phone_only else ""
        if not chosen:
            if phone_only and not any(n.from_phone for n in notices):
                summary = ("I don't see anything from your phone. If it isn't linked yet, open Phone Link on this "
                           "computer and connect it; its notifications then show up here.")
            elif words:
                summary = f"No notifications from {asked} {where}".strip() + "."
            else:
                summary = f"No new notifications {where}".strip() + "."
            return {"action": "read_notifications", "success": True, "verified": True, "summary": summary, "error": None}
        now = datetime.now(timezone.utc)
        listing = "\n".join(f"- {n.describe(now)}" for n in chosen[:_SHOWN])
        more = f"\n(and {len(chosen) - _SHOWN} older)" if len(chosen) > _SHOWN else ""
        count = "1 notification" if len(chosen) == 1 else f"{len(chosen)} notifications"
        return {"action": "read_notifications", "success": True, "verified": True, "error": None,
                "summary": f"{count} {where}".strip() + f":\n{listing}{more}"}


notifications_tool = NotificationsTool()
tool_registry.register_tool(notifications_tool)
