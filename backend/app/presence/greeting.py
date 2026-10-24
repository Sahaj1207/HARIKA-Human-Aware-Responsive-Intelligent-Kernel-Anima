"""Greetings and small talk ("hi", "good morning", "how are you?") that sound like a person, not a script.

The conversation model writes the reply, given the moment: the user's name, the time
of day, how long since they last talked, what's coming up today (from the user's own
reminders, calendar and people), one thing HARIKA remembers about them, and its own
last few greetings so it doesn't repeat itself. It is told to use at most one of
those things and never to state anything that isn't there.

If the model is local (slow to answer) or doesn't answer within a few seconds, a
short greeting fitting the time of day is used instead, so a hello is never slow.
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import List, Optional

from app.core.paths import data_path

logger = logging.getLogger("harika.presence.greeting")

_TIMEOUT = 4.0
_REMEMBER = 6  # recent greetings kept, so none is repeated soon
_TURNS = 6  # conversation turns passed along
_PROMPT = """You are HARIKA, a warm personal assistant who lives on {name_or_their} computer, answering a greeting or
small talk. Reply like a friend who is also their assistant: one or two short, natural, spoken sentences, never
the same shape twice. Start with one tone tag: [cheerful], [warm], [calm], [playful] or [empathetic].

The moment, for you to use only if it fits naturally (most replies mention at most one thing from it, often
nothing; never list them, never turn a hello into a briefing):
{context}

Rules: mention only facts given above, never invent plans, weather, news or events. If they ask how you are,
answer briefly like a person and turn it back to them. If they ask what you can do or help with, give a short,
friendly overview: a handful of highlights in one or two sentences, then offer to say more about any of them; if
they ask about one area (music, email, files...), answer about just that. Never recite the whole list. What you
can do: {abilities}. Plain text, no emoji. Don't repeat or closely echo any of these recent replies:
{recent}"""


def _part_of_day(now: datetime) -> str:
    hour = now.hour
    if hour < 5:
        return "late at night"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 21:
        return "evening"
    return "night"


def _name(user_id: str) -> str:
    return "" if (user_id or "").strip().lower() in ("", "default", "user") else user_id.strip()


class Greeter:
    def __init__(self, state_path=None):
        self.state_path = state_path or data_path("memory", "greetings.json")

    # ------------------------------------------------------------- recent replies

    def recent(self) -> List[str]:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))[-_REMEMBER:]
        except (OSError, ValueError):
            return []

    def _remember(self, text: str) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps((self.recent() + [text])[-_REMEMBER:]), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------- the moment

    async def context(self, user_id: str, now: datetime) -> List[str]:
        lines = [f"It's {now:%A}, {_part_of_day(now)} ({now.strftime('%I:%M %p').lstrip('0')})."]
        name = _name(user_id)
        if name:
            lines.append(f"Their name is {name}.")
        lines.append(self._since_last_talk(now))
        lines += await self._today(now)
        fact = self._a_memory(user_id)
        if fact:
            lines.append(f"Something you remember about them: {fact}")
        return [line for line in lines if line]

    @staticmethod
    def _since_last_talk(now: datetime) -> str:
        from app.memory.journal import journal

        for day in reversed(journal.days()):
            entries = journal.entries(day)
            if entries:
                last = datetime.fromisoformat(entries[-1]["time"])
                gap = now - last
                if gap < timedelta(minutes=10):
                    return "You were talking with them a few minutes ago."
                if last.date() != now.date():
                    days = (now.date() - last.date()).days
                    return "This is the first time you've talked today." if days == 1 else f"You last talked {days} days ago."
                return f"You last talked about {int(gap.total_seconds() // 3600) or 1} hour(s) ago."
        return "This is one of your first conversations."

    @staticmethod
    async def _today(now: datetime) -> List[str]:
        out: List[str] = []
        try:
            from app.tools.system.reminders import reminders_tool
            later = [r for r in reminders_tool.store.pending()
                     if datetime.fromisoformat(r["due"]).date() == now.date() and r["text"].lower() != "timer"]
            if later:
                due = datetime.fromisoformat(later[0]["due"])
                out.append(f"Their next reminder today: {later[0]['text']} at {due.strftime('%I:%M %p').lstrip('0')}.")
        except Exception:
            pass
        try:
            from app.tools.productivity.people_tool import people_store
            names = [p["name"] for p, when, _ in people_store.birthdays(now.date(), within_days=0) if when == now.date()]
            if names:
                out.append(f"It's {', '.join(names)}'s birthday today.")
        except Exception:
            pass
        try:
            from app.integrations.google.account import google_account
            if google_account.status()["calendar"]:
                from app.integrations.google.calendar import google_calendar
                end = now.replace(hour=23, minute=59)
                events = await asyncio.wait_for(google_calendar.events(now, end, limit=3), timeout=1.5)
                timed = [e for e in events if not e.all_day]
                if timed:
                    out.append(f"Their next event today: {timed[0].title} at {timed[0].start.strftime('%I:%M %p').lstrip('0')}.")
        except Exception:
            pass  # the calendar is a nice touch, never a reason to be slow
        return out

    @staticmethod
    def _a_memory(user_id: str) -> str:
        if random.random() > 0.4:  # only sometimes; a friend doesn't bring something up every time
            return ""
        try:
            from app.memory.manager import memory_manager
            from app.memory.models import MemoryCategory
            facts = [m.content for m in memory_manager.get_memories(user_id=user_id) if m.category != MemoryCategory.EPISODES]
            return random.choice(facts[:20]) if facts else ""
        except Exception:
            return ""

    # ------------------------------------------------------------- replying

    async def reply(self, message: str, user_id: str = "default", now: Optional[datetime] = None, ask=None,
                    about_abilities: bool = False, history: Optional[List[dict]] = None) -> str:
        """The reply, starting with a tone tag. `history` is the conversation so far, so "what else?" gets
        something new."""
        now = now or datetime.now()
        text = ""
        try:
            text = await asyncio.wait_for(self._generate(message, user_id, now, ask, history), timeout=_TIMEOUT)
        except Exception as exc:
            logger.info(f"[Greeting] Using a quick greeting instead: {exc or type(exc).__name__}")
        text = text or self.quick(message, user_id, now, about_abilities)
        self._remember(text)
        return text

    async def _generate(self, message: str, user_id: str, now: datetime, ask=None, history=None) -> str:
        from app.presence.communication.capability import describe_abilities

        name = _name(user_id)
        system = _PROMPT.format(
            name_or_their=f"{name}'s" if name else "the user's",
            context="\n".join(f"- {line}" for line in await self.context(user_id, now)),
            abilities=describe_abilities().split(" Just ask")[0],
            recent="\n".join(f"- {r}" for r in self.recent()) or "- (none yet)",
        )
        if ask:
            return (await ask(system, message)).strip()
        from app.cognition.llm.manager import RoleProvider
        provider = RoleProvider("conversation")
        if provider.is_local():
            return ""  # a local model takes seconds to answer; a hello shouldn't
        turns = [t for t in (history or [])[-_TURNS:] if t.get("role") in ("user", "assistant") and t.get("content")]
        if turns and turns[-1]["role"] == "user" and turns[-1]["content"].strip() == message.strip():
            turns = turns[:-1]  # the app sends the new message as part of the history too
        result = await provider.generate_response(
            [{"role": t["role"], "content": t["content"]} for t in turns] + [{"role": "user", "content": message}], system)
        return "" if result.get("error") else str(result.get("response", "")).strip()

    def quick(self, message: str, user_id: str, now: datetime, about_abilities: bool = False) -> str:
        """A short greeting for the time of day, not one used recently."""
        name = _name(user_id)
        you = f", {name}" if name else ""
        lowered = message.lower()
        if "how are you" in lowered or "how's it going" in lowered or "how is it going" in lowered:
            options = [f"[cheerful] I'm good, thanks{you}! How about you?", f"[warm] Doing well{you}. How's your day going?"]
        elif about_abilities or "help" in lowered:
            options = ["[warm] Lots of things: your apps, music, reminders, calendar, email, messages, notes and the web. What do you need?"]
        else:
            part = _part_of_day(now)
            options = {
                "morning": [f"[cheerful] Good morning{you}! What's first today?", f"[warm] Morning{you}! How can I help?",
                            f"[cheerful] Hi{you}! Ready for the day?", f"[warm] Hey{you}, good morning. What do you need?"],
                "afternoon": [f"[warm] Good afternoon{you}! What can I do for you?", f"[cheerful] Hey{you}! What's up?",
                              f"[warm] Hi{you}! How's the day going?", f"[cheerful] Hello{you}! What are we doing?"],
                "evening": [f"[warm] Good evening{you}! How was your day?", f"[calm] Evening{you}. What can I do for you?",
                            f"[warm] Hey{you}! Done for the day?", f"[cheerful] Hi{you}! What's on your mind?"],
                "night": [f"[calm] Hey{you}. Winding down for the night?", f"[warm] Hi{you}! What do you need?",
                          f"[calm] Hello{you}. Anything before you call it a night?"],
                "late at night": [f"[calm] Still up{you}? What can I do for you?", f"[warm] Hey{you}, it's late. Need anything?",
                                  f"[calm] Hi{you}. Can't sleep?"],
            }[part]
        recent = set(self.recent())
        fresh = [o for o in options if o not in recent] or options
        return random.choice(fresh)


greeter = Greeter()
