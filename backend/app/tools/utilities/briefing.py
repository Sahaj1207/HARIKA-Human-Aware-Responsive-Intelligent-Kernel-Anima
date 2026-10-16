"""The daily briefing: greeting, weather, calendar, reminders, new email and the top headlines.

It is assembled from the weather, reminders and news sources directly (no language
model), so it is quick and every fact in it comes from a source. On request ("brief
me"), and optionally every morning at the time chosen in Settings.
"""
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.daily_settings import daily_settings
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

logger = logging.getLogger("harika.tools.briefing")

_MISSED_WINDOW = timedelta(hours=3)  # a briefing missed while the computer was off still comes, within reason


def _greeting(now: datetime, name: str) -> str:
    part = "morning" if 4 <= now.hour < 12 else "afternoon" if 12 <= now.hour < 17 else "evening"
    return f"Good {part}{', ' + name if name else ''}. It's {now:%A}, {now.day} {now:%B}."


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" and {items[-1]}"


def reminders_today(pending: List[Dict[str, Any]], now: datetime) -> str:
    today = [r for r in pending if datetime.fromisoformat(r["due"]).date() == now.date()]
    if not today:
        return "Nothing on your reminders for today."
    items = [
        "a timer" if r["text"].lower() == "timer"
        else f"{r['text']} at {datetime.fromisoformat(r['due']).strftime('%I:%M %p').lstrip('0')}"
        for r in today[:4]
    ]
    count = f"{len(today)} reminders" if len(today) > 1 else "one reminder"
    return f"You have {count} today: {_join(items)}."


async def _skip() -> str:
    return ""


def headlines_text(items: List[Dict[str, str]]) -> str:
    if not items:
        return ""
    return "In the news: " + "; ".join(item["title"] for item in items[:3]) + "."


async def build_briefing(name: str = "", now: Optional[datetime] = None) -> Dict[str, Any]:
    """Each part is independent: one that can't be fetched is left out, never invented."""
    from app.tools.system.reminders import reminders_tool
    from app.tools.web import sources
    from app.tools.web.weather import locator, weather_tool

    now = now or datetime.now()

    async def weather() -> str:
        place = await locator.resolve("here")
        return (await weather_tool.report(place, 0))["summary"]

    async def news() -> List[Dict[str, str]]:
        return await sources.news(None, await locator.country_code(), 3)

    async def calendar() -> str:
        from app.integrations.google.calendar import google_calendar
        from app.tools.productivity.calendar_tool import describe_day
        return describe_day(await google_calendar.day(now.date()), "today")

    async def inbox() -> str:
        from app.integrations.google.gmail import gmail
        mails = await gmail.unread(5)
        if not mails:
            return "No new email."
        senders = list(dict.fromkeys(m.sender_name for m in mails))
        count = "one new email" if len(mails) == 1 else f"{'at least ' if len(mails) == 5 else ''}{len(mails)} new emails"
        return f"You have {count}, from {_join(senders[:3])}."

    from app.integrations.google.account import google_account
    account = google_account.status()
    weather_text, headlines, events, emails = await asyncio.gather(
        weather(), news(),
        calendar() if account["calendar"] else _skip(),
        inbox() if account["email_read"] else _skip(),
        return_exceptions=True,
    )
    parts = [_greeting(now, name)]
    if isinstance(weather_text, str):
        parts.append(weather_text)
    if isinstance(events, str) and events:
        parts.append(events)
    parts.append(reminders_today(reminders_tool.store.pending(), now))
    if isinstance(emails, str) and emails:
        parts.append(emails)
    news_items = headlines if isinstance(headlines, list) else []
    if news_items:
        parts.append(headlines_text(news_items))
    if not isinstance(weather_text, str) and not news_items:
        parts.append("I couldn't reach the internet for the weather and news.")
    return {"text": "\n\n".join(parts), "headlines": news_items}


class BriefingTool(BaseTool):
    manifest = ToolManifest(
        name="briefing",
        display_name="Daily briefing",
        description="Gives a short briefing for the day: weather, today's reminders and the top headlines.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["daily_briefing"],
        operations={"brief": "daily_briefing"},
        default_targets={"brief": "today"},
        target_aliases={"today": ["today", "my day", "the day", "morning", "briefing", "daily briefing"]},
        ability="give you a daily briefing",
        target_description="'today'",
    )
    timeout_seconds = 30.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Weather, reminders and news", dependencies=["httpx"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        return "today", 0.9

    def describe_action(self, args: Dict[str, Any]) -> str:
        return "give you your briefing"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return {"dry_run": True, "action": "daily_briefing"}
        briefing = await build_briefing(_user_name())
        from app.tools import recent_results
        recent_results.remember("web", [{"url": h["url"], "title": h["title"]} for h in briefing["headlines"]])
        return {"action": "daily_briefing", "success": True, "verified": True,
                "summary": briefing["text"], "error": None}


def _user_name() -> str:
    try:
        from app.voice.engine import voice_engine
        name = (voice_engine.settings.load().get("user_name") or "").strip()
        return "" if name.lower() in ("user", "default") else name  # placeholders, not a name
    except Exception:
        return ""


def briefing_due(settings: Dict[str, Any], now: datetime) -> bool:
    if not settings["briefing_enabled"] or settings["last_briefing"] == now.date().isoformat():
        return False
    hour, minute = (int(part) for part in settings["briefing_time"].split(":"))
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return scheduled <= now < scheduled + _MISSED_WINDOW


async def run_briefing_scheduler(interval_seconds: float = 30.0) -> None:
    """Deliver the morning briefing once a day: in HARIKA's windows, as a notification, and spoken."""
    from app.core.live_events import live_events
    from app.tools.system.reminders import show_os_notification

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            now = datetime.now()
            if not briefing_due(daily_settings.load(), now):
                continue
            daily_settings.update(last_briefing=date.today().isoformat())
            briefing = await build_briefing(_user_name(), now)
            live_events.publish("briefing", text=briefing["text"])
            await asyncio.to_thread(show_os_notification, "HARIKA", briefing["text"].split("\n\n")[0])
            await asyncio.to_thread(_speak, briefing["text"])
            logger.info("[Briefing] Delivered the daily briefing.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"[Briefing] Scheduled briefing failed: {exc}")


def _speak(text: str) -> None:
    from app.voice.engine import voice_engine

    if voice_engine.ready() and voice_engine.settings.load()["speak_replies"] != "never":
        voice_engine.speak(text)


briefing_tool = BriefingTool()
tool_registry.register_tool(briefing_tool)
