import asyncio
import inspect
import json
import logging
import re
import threading
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.cognition.semantic.catalog import CapabilityCatalog
from app.cognition.semantic.contract import (
    MinimalSemanticIntent,
    ResolvedStep,
    SemanticAction,
    SemanticPlan,
    SemanticRequest,
)

logger = logging.getLogger("harika.semantic.interpreter")

class SemanticInterpretationError(ValueError):
    """The provider response cannot safely become a semantic request."""


class SemanticTimeoutError(SemanticInterpretationError):
    """The model did not answer in time (typically still loading or re-reading its prompt)."""


class LLMResponseProvider(ABC):
    """Minimal adapter over HARIKA's existing async LLM provider contract."""

    @abstractmethod
    async def generate_response(self, messages, system_prompt):
        raise NotImplementedError


_PROMPT_TEMPLATE = """You are the language-understanding layer of HARIKA, a desktop AI assistant.
Decide whether the user's message asks HARIKA to perform actions on the computer, and if so which ones, in order.

Operations HARIKA can perform (use these operation names exactly):
{operations}

Reply with STRICT JSON only, in this shape:
{{"actions": [{{"operation": "<operation>", "target": "<plain-language target>", "parameters": {{...}}}}]}}
Leave out "parameters" when there are none.

Rules:
- List actions in the order the user wants them done. Most messages have one action.
- "target" is what the user means in plain words, normalized: fix abbreviations and typos ("calci" -> "calculator").
- "it", "that" or "the app" mean the most recent matching thing in the recent context below; output its name, never "it".
- Times: use "in_seconds"/"in_minutes"/"in_hours" for relative times; for clock times use "at" as 24-hour "HH:MM" today, or "YYYY-MM-DDTHH:MM" for another day (use the current local time below).
- Questions whose answer depends on recent or live information (news, scores, results, prices, releases, what someone did lately, anything that may have changed since your training) use "answer"; the weather and forecasts use "weather". "search", "google" or "look up" in a browser stays "search". Doing something on a website for the user (ordering, adding to a cart, booking, filling in a form, finding something on a site and reporting back) uses "web".
- The user telling you about their own plans or deadlines ("I'll call the bank on Monday", "I need to submit the form by Friday") is conversation: set reminders or calendar events only when they ask for one.
- Questions about earlier conversations with HARIKA (what we talked about, what the user said, did or decided on a past day or about a topic) use "recall".
- If the message is conversation, a timeless knowledge question, a request to remember something, a question about the user's own facts ("what's my favourite food?"), planning, or anything not covered by the operations above, reply {{"actions": []}}.
- Never output shell commands, code, file paths, or any keys other than operation, target and parameters.

Examples:
"bring up the calculator" -> {{"actions": [{{"operation": "open", "target": "calculator"}}]}}
"I need to use calci" -> {{"actions": [{{"operation": "open", "target": "calculator"}}]}}
"quit chrome" -> {{"actions": [{{"operation": "close", "target": "chrome"}}]}}
"google cheap flights to Delhi" -> {{"actions": [{{"operation": "search", "target": "cheap flights to Delhi"}}]}}
"grab a screenshot of this" -> {{"actions": [{{"operation": "screenshot"}}]}}
"make it louder" -> {{"actions": [{{"operation": "increase", "target": "volume"}}]}}
"skip this track" -> {{"actions": [{{"operation": "next", "target": "music"}}]}}
"put the computer to sleep" -> {{"actions": [{{"operation": "sleep"}}]}}
"play something relaxing on spotify" -> {{"actions": [{{"operation": "play_for_me", "target": "relaxing", "parameters": {{"platform": "spotify"}}}}]}}
"play something I'd like" -> {{"actions": [{{"operation": "play_for_me", "target": "anything"}}]}}
"put on some music for coding" -> {{"actions": [{{"operation": "play_for_me", "target": "coding"}}]}}
"what kind of music am I into?" -> {{"actions": [{{"operation": "music_taste", "target": "me"}}]}}
"play some Arijit Singh on spotify" -> {{"actions": [{{"operation": "play", "target": "Arijit Singh", "parameters": {{"platform": "spotify", "kind": "artist"}}}}]}}
"play my liked songs" -> {{"actions": [{{"operation": "play_library", "target": "liked songs"}}]}}
"put on my workout playlist" -> {{"actions": [{{"operation": "play_library", "target": "workout"}}]}}
"what's this song?" -> {{"actions": [{{"operation": "now_playing", "target": "spotify"}}]}}
"I love this song, save it" -> {{"actions": [{{"operation": "like_song", "target": "current song"}}]}}
"add this to my road trip playlist" -> {{"actions": [{{"operation": "add_to_playlist_spotify", "target": "road trip"}}]}}
"play Believer next" -> {{"actions": [{{"operation": "queue_song", "target": "Believer"}}]}}
"queue up Levitating by Dua Lipa" -> {{"actions": [{{"operation": "queue_song", "target": "Levitating by Dua Lipa"}}]}}
"add 1 kg basmati rice to my amazon cart" -> {{"actions": [{{"operation": "web", "target": "add 1 kg basmati rice to my Amazon cart"}}]}}
"how much is the PS5 on flipkart right now?" -> {{"actions": [{{"operation": "web", "target": "check the price of the PS5 on Flipkart"}}]}}
"reserve a table for 4 at 8pm on swiggy dineout" -> {{"actions": [{{"operation": "web", "target": "reserve a table for 4 at 8pm on Swiggy Dineout"}}]}}
"find me flights from hyderabad to goa this saturday on google flights" -> {{"actions": [{{"operation": "web", "target": "find flights from Hyderabad to Goa this Saturday on Google Flights"}}]}}
"join my call" -> {{"actions": [{{"operation": "join_meeting", "target": "current"}}]}}
"open my meeting link" -> {{"actions": [{{"operation": "join_meeting", "target": "current"}}]}}
"open the design review meeting from my calendar" -> {{"actions": [{{"operation": "join_meeting", "target": "design review"}}]}}
"open chrome, look up F1 news and open the first result" -> {{"actions": [{{"operation": "open", "target": "chrome"}}, {{"operation": "search", "target": "F1 news"}}, {{"operation": "open", "target": "first result"}}]}}
"open instagram in chrome" -> {{"actions": [{{"operation": "open", "target": "instagram.com", "parameters": {{"browser": "chrome"}}}}]}}
"open my resume" -> {{"actions": [{{"operation": "open", "target": "resume"}}]}}
"summarise my resume" -> {{"actions": [{{"operation": "ask_file", "target": "resume", "parameters": {{"question": "summarise it"}}}}]}}
"can you summarize the youtube video I have open" -> {{"actions": [{{"operation": "video", "target": "this video", "parameters": {{"question": "summarise it"}}}}]}}
"what's this video about?" -> {{"actions": [{{"operation": "video", "target": "this video", "parameters": {{"question": "summarise it"}}}}]}}
"what does the video say about recursion?" -> {{"actions": [{{"operation": "video", "target": "this video", "parameters": {{"question": "what does it say about recursion?"}}}}]}}
"sum up this one for me: youtu.be/dQw4w9WgXcQ" -> {{"actions": [{{"operation": "video", "target": "https://youtu.be/dQw4w9WgXcQ", "parameters": {{"question": "summarise it"}}}}]}}
"what does the lease say about the deposit?" -> {{"actions": [{{"operation": "ask_file", "target": "lease", "parameters": {{"question": "what does it say about the deposit?"}}}}]}}
"what's in the file I just downloaded?" -> {{"actions": [{{"operation": "ask_file", "target": "latest download", "parameters": {{"question": "what's in it?"}}}}]}}
"compare my old resume with the new one" -> {{"actions": [{{"operation": "compare_files", "target": "old resume", "parameters": {{"other": "new resume", "question": "what changed?"}}}}]}}
"clean up my downloads" -> {{"actions": [{{"operation": "tidy", "target": "downloads"}}]}}
"get rid of old installers on my desktop" -> {{"actions": [{{"operation": "tidy", "target": "desktop", "parameters": {{"kinds": ["installers"]}}}}]}}
"any new messages on my phone?" -> {{"actions": [{{"operation": "notifications", "target": "phone"}}]}}
"what did Mom text me?" -> {{"actions": [{{"operation": "notifications", "target": "Mom", "parameters": {{"phone": true}}}}]}}
"did I miss any notifications?" -> {{"actions": [{{"operation": "notifications", "target": "all"}}]}}
"anything new on Instagram?" -> {{"actions": [{{"operation": "notifications", "target": "Instagram"}}]}}
"where is my tax pdf" -> {{"actions": [{{"operation": "find", "target": "tax pdf"}}]}}
"remind me to drink water at 4:15 pm" -> {{"actions": [{{"operation": "remind", "target": "drink water", "parameters": {{"at": "16:15"}}}}]}}
"remind me to call Ravi in half an hour" -> {{"actions": [{{"operation": "remind", "target": "call Ravi", "parameters": {{"in_minutes": 30}}}}]}}
"cancel my stretch reminder" -> {{"actions": [{{"operation": "cancel", "target": "stretch"}}]}}
"start a 10 minute timer" -> {{"actions": [{{"operation": "remind", "target": "timer", "parameters": {{"in_minutes": 10}}}}]}}
"do I have any timers running?" -> {{"actions": [{{"operation": "list", "target": "reminders"}}]}}
"continue this chat" -> {{"actions": [{{"operation": "reply", "target": "this chat"}}]}}
"reply that I'll be 10 minutes late" -> {{"actions": [{{"operation": "reply", "target": "this chat", "parameters": {{"instruction": "say I'll be 10 minutes late"}}}}]}}
"make it more casual" (after a chat draft) -> {{"actions": [{{"operation": "reply", "target": "this chat", "parameters": {{"instruction": "make it more casual"}}}}]}}
"what's on my screen?" -> {{"actions": [{{"operation": "read", "target": "screen"}}]}}
"what does this chart show?" -> {{"actions": [{{"operation": "read", "target": "screen", "parameters": {{"look": true}}}}]}}
"what's the latest F1 news?" -> {{"actions": [{{"operation": "answer", "target": "latest Formula 1 news"}}]}}
"who won the match yesterday" -> {{"actions": [{{"operation": "answer", "target": "who won yesterday's match"}}]}}
"how's the weather" -> {{"actions": [{{"operation": "weather", "target": "here"}}]}}
"will it rain in Mumbai tomorrow?" -> {{"actions": [{{"operation": "weather", "target": "Mumbai", "parameters": {{"day": "tomorrow"}}}}]}}
"brief me" / "what does my day look like?" -> {{"actions": [{{"operation": "brief", "target": "today"}}]}}
"how was my day?" / "wrap up my day" -> {{"actions": [{{"operation": "wrap_up", "target": "today"}}]}}
"what's on my calendar tomorrow?" -> {{"actions": [{{"operation": "agenda", "target": "tomorrow"}}]}}
"add dentist on Friday at 5pm" -> {{"actions": [{{"operation": "schedule", "target": "Dentist", "parameters": {{"at": "<that Friday as YYYY-MM-DD>T17:00"}}}}]}}
"cancel the team lunch on Friday" -> {{"actions": [{{"operation": "unschedule", "target": "team lunch"}}]}} (an event on the calendar, not a reminder)
"move my dentist appointment to 6" -> {{"actions": [{{"operation": "reschedule", "target": "dentist", "parameters": {{"at": "18:00"}}}}]}}
"any new emails?" -> {{"actions": [{{"operation": "check_email", "target": "inbox"}}]}}
"did Priya email me about the trip?" -> {{"actions": [{{"operation": "check_email", "target": "Priya trip"}}]}}
"read the second one" (after listing emails) ->{{"actions": [{{"operation": "read_email", "target": "2"}}]}}
"email Priya that I'll be late tonight" -> {{"actions": [{{"operation": "email", "target": "Priya", "parameters": {{"instruction": "say I'll be late tonight"}}}}]}}
"reply saying thanks, I'll be there" (after reading an email) -> {{"actions": [{{"operation": "reply_email", "target": "it", "parameters": {{"instruction": "say thanks, I'll be there"}}}}]}}
"make it shorter" (after an email draft) -> {{"actions": [{{"operation": "email", "target": "it", "parameters": {{"instruction": "make it shorter"}}}}]}}
"when I say good night, mute and close chrome" -> {{"actions": [{{"operation": "create_routine", "target": "good night", "parameters": {{"steps": "mute the volume and close chrome"}}}}]}}
"every weekday at 9 open slack and play lofi" -> {{"actions": [{{"operation": "create_routine", "target": "weekday morning", "parameters": {{"steps": "open slack and play lofi", "at": "09:00", "days": "weekdays"}}}}]}}
"start my work routine" -> {{"actions": [{{"operation": "run_routine", "target": "work"}}]}}
"Mom's number is +91 98765 43210" -> {{"actions": [{{"operation": "remember_person", "target": "Mom", "parameters": {{"phone": "+91 98765 43210"}}}}]}}
"Priya is my best friend, her birthday is 12 March" -> {{"actions": [{{"operation": "remember_person", "target": "Priya", "parameters": {{"relation": "best friend", "birthday": "--03-12"}}}}]}}
"remember my favourite food is dosa" -> {{"actions": []}} (the user's own likes are memories, not people)
"when is Priya's birthday?" -> {{"actions": [{{"operation": "person_info", "target": "Priya", "parameters": {{"field": "birthday"}}}}]}}
"text Mom that I'm on my way" -> {{"actions": [{{"operation": "message", "target": "Mom", "parameters": {{"text": "I'm on my way"}}}}]}}
"tell Priya I'll call her after class" -> {{"actions": [{{"operation": "message", "target": "Priya", "parameters": {{"text": "I'll call you after class"}}}}]}}
"remind me to ask Priya about the tickets when I talk to her" -> {{"actions": [{{"operation": "remind", "target": "ask Priya about the tickets", "parameters": {{"person": "Priya"}}}}]}}
"I'll call the bank on Monday" -> {{"actions": []}}
"my project report is due on Thursday" -> {{"actions": []}}
"remind me to drink water when I'm back" -> {{"actions": [{{"operation": "remind", "target": "drink water", "parameters": {{"when": "back"}}}}]}}
"take a note: the wifi password is on the fridge" -> {{"actions": [{{"operation": "note", "target": "the wifi password is on the fridge"}}]}}
"add milk and eggs to my shopping list" -> {{"actions": [{{"operation": "add_to_list", "target": "milk", "parameters": {{"list": "shopping", "items": ["milk", "eggs"]}}}}]}}
"what's on my to-do list?" -> {{"actions": [{{"operation": "show_list", "target": "to-do"}}]}}
"clear my notes" -> {{"actions": [{{"operation": "clear_list", "target": "notes"}}]}}
"I bought the milk" (after a shopping list) -> {{"actions": [{{"operation": "check_off", "target": "milk", "parameters": {{"list": "shopping"}}}}]}}
"how much battery is left?" -> {{"actions": [{{"operation": "battery", "target": "battery"}}]}}
"turn off bluetooth" -> {{"actions": [{{"operation": "turn_off", "target": "bluetooth"}}]}}
"switch to chrome" -> {{"actions": [{{"operation": "switch_to", "target": "chrome"}}]}}
"research laptops under 60k for coding and compare the best three" -> {{"actions": [{{"operation": "task", "target": "compare the best three laptops under 60000 rupees for coding"}}]}}
"plan a weekend trip to Goa" -> {{"actions": [{{"operation": "task", "target": "plan a weekend trip to Goa"}}]}}
"find a free hour next week for the dentist and add it" -> {{"actions": [{{"operation": "task", "target": "find a free hour next week for a dentist appointment and add it to my calendar"}}]}}
"can you see the screen and notify me when Claude finishes the work?" -> {{"actions": [{{"operation": "watch", "target": "claude"}}]}} ("can you see" only leads into the request)
"tell me when chrome says download complete" -> {{"actions": [{{"operation": "watch", "target": "chrome", "parameters": {{"text": "download complete"}}}}]}}
"stop watching" -> {{"actions": [{{"operation": "stop_watching", "target": "all"}}]}}
"what did we talk about yesterday?" -> {{"actions": [{{"operation": "recall", "target": "everything", "parameters": {{"day": "yesterday"}}}}]}}
"what did I decide about the trip?" -> {{"actions": [{{"operation": "recall", "target": "the trip"}}]}}
"what was that laptop we looked at last week?" -> {{"actions": [{{"operation": "recall", "target": "laptop"}}]}}
"what is the capital of France?" -> {{"actions": []}}
"remember that I like cricket" -> {{"actions": []}}
{context}"""


_ALWAYS = ('"what is the capital of France?"', '"remember that I like cricket"')  # teach "this is conversation"


def prompt_examples() -> List[str]:
    return [line for line in _PROMPT_TEMPLATE.partition("Examples:\n")[2].splitlines() if line.startswith('"')]


def select_abilities(operations: str, message: str) -> "Selection":
    from app.cognition.semantic.embedder import embedder
    from app.cognition.semantic.selection import AbilitySelector
    return AbilitySelector(embedder).select(message, operations, prompt_examples(), _ALWAYS)


def _replying_to(context: Optional[Any]) -> List[str]:
    """HARIKA's latest messages within the turns the model is shown (at most two), which a short reply
    may be answering."""
    said = [str(turn.get("content", "")).strip()[:300]
            for turn in list(getattr(context, "conversation_history", None) or [])[-4:]
            if (turn.get("role") or turn.get("sender")) == "assistant" and str(turn.get("content", "")).strip()]
    return said[-2:]


def _top_operations(operations: str, text: str, abilities: int = 2) -> set:
    """The operations of the abilities `text` is most about (two: one word, like an app's name, can
    outweigh what the message is really about)."""
    from app.cognition.semantic.selection import CONVERSATION, parse_groups
    selection = select_abilities(operations, text)
    if not selection.confident:
        return set()
    groups = {g.name: g for g in parse_groups(operations, prompt_examples())}
    top = [groups[name] for name, _ in selection.scores if name in groups and name != CONVERSATION][:abilities]
    return {op for group in top for op in group.operations}


def _short(text: str, limit: int = 34) -> str:
    """The start of a description, cut at a word boundary."""
    text = text.split(". ")[0].rstrip(".")
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def compact_prompt(operations: str, context_block: str, message: str, selection: Optional["Selection"] = None) -> str:
    """The same instructions, cut down for one message: full details and examples for the abilities
    that fit it (chosen by meaning, see selection.py) and one line for every other ability."""
    selection = selection or select_abilities(operations, message)
    head = _PROMPT_TEMPLATE.partition("Examples:\n")[0]
    lines = []
    for line in operations.splitlines():
        names = set(re.findall(r'"([a-z_]+)"', line.split(":", 1)[0]))
        if names & selection.operations:
            lines.append(line)
        else:
            # Abilities that don't fit this message only need to be known about: a short phrase each
            # keeps the request small (free tiers count every token).
            summary = line.split(":", 1)[1].split(" Target:")[0].strip() if ":" in line else line
            lines.append(f"{line.split(':', 1)[0]}: {_short(summary)}")
    template = head + "Examples:\n" + "\n".join(selection.examples) + "\n{context}"
    return template.format(operations="\n".join(lines), context=context_block)


class SemanticInterpreter:
    """Interprets language only; it cannot execute or invoke capabilities."""

    def __init__(self, provider: LLMResponseProvider, catalog: CapabilityCatalog, timeout_seconds: float = 10.0):
        self.provider = provider
        self.catalog = catalog
        self.timeout_seconds = timeout_seconds

    async def interpret(
        self,
        raw_text: str,
        context: Optional[Any] = None,
        hints: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> SemanticRequest:
        # Cloud models get a shorter prompt (free tiers count every token); a local model keeps
        # the full, unchanging prompt so it can reuse what it has already read.
        is_local = getattr(self.provider, "is_local", None)
        compact = callable(is_local) and not is_local()
        selection = await self._select(raw_text, _replying_to(context)) if compact else None
        prompt = self._build_prompt(context, hints, message=raw_text if compact else "", selection=selection)
        limit = timeout or self.timeout_seconds
        kwargs = {}
        if "json_mode" in inspect.signature(self.provider.generate_response).parameters:
            kwargs["json_mode"] = True
        try:
            result = await asyncio.wait_for(
                self.provider.generate_response(
                    messages=[{"role": "user", "content": raw_text}],
                    system_prompt=prompt,
                    **kwargs,
                ),
                timeout=limit,
            )
        except asyncio.TimeoutError as exc:
            raise SemanticTimeoutError(
                f"LLM semantic interpretation timed out after {limit:.2f}s."
            ) from exc
        response = result.get("response") if isinstance(result, dict) else None
        payload = self._parse_json(response)
        self._reject_unsafe_payload(payload)
        return self._normalize_payload(raw_text, payload)

    async def interpret_confirmation(self, reply: str, question: str) -> str:
        """Classify a reply to a yes/no question as 'confirm', 'decline', 'revise' or 'other'.

        Approval must be explicit and unconditional: anything that asks for a
        change is 'revise', anything else that isn't a plain yes or no is 'other',
        and the model must also state it is certain before 'confirm' counts.
        """
        prompt = (
            "HARIKA asked the user this question before doing something on their computer:\n"
            f"\"{question}\"\n\n"
            "Classify the user's reply. Reply with STRICT JSON only, in this shape:\n"
            '{"decision": "confirm" | "decline" | "revise" | "other", "certain": true | false}\n\n'
            "- confirm: plain, unconditional approval to do exactly what was asked. "
            "Examples: yes; send it; go ahead; sure; do it; yes please; ok send.\n"
            "- decline: refusal. Examples: no; don't; cancel; stop; never mind; don't send it.\n"
            "- revise: asks to change what HARIKA proposed (its wording, length, tone or details) instead of approving it. "
            "Examples: make it shorter; more casual; add a smiley; yes but make it friendlier; mention the deadline; "
            "say it more politely.\n"
            "- other: anything else: a question, a new topic, or a different action. "
            "Examples: what time is it; open Spotify; send it to Mom instead; change the time to 8.\n"
            "Set certain to true only if the reply clearly belongs to that category."
        )
        kwargs = {}
        if "json_mode" in inspect.signature(self.provider.generate_response).parameters:
            kwargs["json_mode"] = True
        result = await asyncio.wait_for(
            self.provider.generate_response(messages=[{"role": "user", "content": reply}], system_prompt=prompt, **kwargs),
            timeout=self.timeout_seconds,
        )
        payload = self._parse_json(result.get("response") if isinstance(result, dict) else None)
        decision = str(payload.get("decision", "other")).lower()
        if decision == "confirm" and payload.get("certain") is not True:
            return "other"  # an uncertain "yes" never runs a risky action
        return decision if decision in {"confirm", "decline", "revise"} else "other"

    def interpret_sync(self, raw_text: str, context: Optional[Any] = None, hints: Optional[Dict[str, Any]] = None) -> SemanticRequest:
        """Bridge for synchronous callers; async callers should await interpret()."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.interpret(raw_text, context, hints))

        result: Dict[str, Any] = {}
        error: Dict[str, BaseException] = {}

        def runner():
            try:
                result["value"] = asyncio.run(self.interpret(raw_text, context, hints))
            except BaseException as exc:  # re-raise in caller thread
                error["value"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "value" in error:
            raise error["value"]
        return result["value"]

    async def _select(self, message: str, replying_to: Optional[List[str]] = None):
        """The abilities to explain for this message. When the choice is unclear, the language
        model picks from the one-line menu first (one short extra call, only in that case).

        A short reply often only makes sense next to what HARIKA just said ("Want me to open the
        meeting?" -> "tokenmaxxing on claude"), so the ability that message was about is shown too."""
        from app.cognition.semantic.embedder import embedder
        from app.cognition.semantic.selection import AbilitySelector

        operations = self.catalog.describe_operations() or ""
        try:
            selection = await asyncio.to_thread(select_abilities, operations, message)
            context_ops = set()
            for said in replying_to or []:
                context_ops |= await asyncio.to_thread(_top_operations, operations, said)
        except Exception as exc:
            logger.warning(f"[SemanticInterpreter] Ability selection failed: {exc}")
            return None
        if not selection.confident:
            picked = await self._pick_operations(message, operations)
            if picked is not None:
                selection = AbilitySelector(embedder).with_operations(picked, message, operations, prompt_examples(), _ALWAYS)
        if context_ops - selection.operations:
            selection = AbilitySelector(embedder).with_operations(selection.operations | context_ops, message, operations,
                                                                  prompt_examples(), _ALWAYS)
        return selection

    async def _pick_operations(self, message: str, operations: str) -> Optional[set]:
        known = set(re.findall(r'"([a-z_]+)"', "\n".join(line.split(":", 1)[0] for line in operations.splitlines())))
        menu = "\n".join(f"{line.split(':', 1)[0]}: {line.split(':', 1)[1].split(' Target:')[0].strip()[:110]}"
                         for line in operations.splitlines() if ":" in line)
        prompt = (
            "You choose which of HARIKA's abilities a user's message needs. Abilities, by operation name:\n"
            f"{menu}\n\n"
            'Reply with STRICT JSON only: {"operations": ["<operation>", ...]} listing the operations the message '
            'asks for, in order, or {"operations": []} if it is conversation, a question to answer from knowledge, '
            "or anything none of these do."
        )
        kwargs = {}
        if "json_mode" in inspect.signature(self.provider.generate_response).parameters:
            kwargs["json_mode"] = True
        try:
            result = await asyncio.wait_for(self.provider.generate_response(
                messages=[{"role": "user", "content": message}], system_prompt=prompt, **kwargs), timeout=15.0)
            payload = self._parse_json(result.get("response") if isinstance(result, dict) else None)
        except Exception as exc:
            logger.info(f"[SemanticInterpreter] Ability pick skipped: {exc}")
            return None
        names = payload.get("operations") if isinstance(payload, dict) else None
        if not isinstance(names, list):
            return None
        return {str(n) for n in names if str(n) in known}

    def _build_prompt(self, context: Optional[Any], hints: Optional[Dict[str, Any]] = None, message: str = "",
                      selection: Optional[Any] = None) -> str:
        operations = self.catalog.describe_operations() or "- (no actions are currently available)"
        lines: List[str] = []
        history = list(getattr(context, "conversation_history", None) or [])[-4:]
        for turn in history:
            role = turn.get("role") or turn.get("sender") or "user"
            content = str(turn.get("content", "")).strip()
            if content:
                lines.append(f"{role}: {content[:200]}")
        recent = list((hints or {}).get("recent_actions", []))[-3:]
        if recent:
            # Newest first and explicitly labelled: small models otherwise lose track of "it".
            lines.append(f"The last thing HARIKA did: {recent[-1]}")
            if len(recent) > 1:
                lines.append("Before that: " + "; ".join(reversed(recent[:-1])))
        people = list((hints or {}).get("people") or [])
        if people:
            lines.append("People the user has told HARIKA about: " + "; ".join(people) + ". Use these names as targets.")
        routines = list((hints or {}).get("routines") or [])
        if routines:
            lines.append(
                "The user's saved routines: " + "; ".join(routines) +
                ". A message asking for one of these runs it (run_routine with its name)."
            )
        if (hints or {}).get("spoken"):
            lines.append(
                "This message came from speech recognition, so some words may be misheard "
                "(for example \"note bed\" for \"notepad\"). Use the most likely intended words."
            )
        # Kept last so the long, stable part of the prompt stays in the model's cache.
        lines.append(f"Current local time: {datetime.now():%A %Y-%m-%d %H:%M}")
        context_block = "\nRecent context:\n" + "\n".join(lines) + "\n"
        if message:
            return compact_prompt(operations, context_block, message, selection)
        return _PROMPT_TEMPLATE.format(operations=operations, context=context_block)

    def _normalize_payload(self, raw_text: str, payload: Dict[str, Any]) -> SemanticRequest:
        if "actions" in payload:
            try:
                plan = SemanticPlan.model_validate(payload)
            except Exception as exc:
                raise SemanticInterpretationError(f"Invalid semantic action list: {exc}") from exc
            actions = plan.actions
        else:
            try:
                intent = MinimalSemanticIntent.model_validate(payload)
            except Exception as exc:
                raise SemanticInterpretationError(f"Invalid minimal semantic intent: {exc}") from exc
            actions = [SemanticAction(operation=intent.operation, target=intent.target, parameters=intent.parameters, goal=intent.goal)]

        if not actions:
            return SemanticRequest(raw_text=raw_text, probable_goal="conversation", confidence=0.9, is_conversational=True)

        steps: List[ResolvedStep] = []
        unresolved: List[SemanticAction] = []
        for action in actions:
            operation = action.operation.strip().lower()
            target = action.target or action.parameters.get("query")
            resolution = self.catalog.resolve_action(operation, target)
            if not resolution.supported:
                unresolved.append(action)
                continue
            steps.append(ResolvedStep(
                operation=operation,
                target=resolution.target,
                parameters=dict(action.parameters),
                capability=resolution.capability,
                tool_name=resolution.tool_name,
                arguments=dict(resolution.arguments),
                confidence=resolution.confidence,
            ))

        first = actions[0]
        entities = dict(first.parameters)
        if first.target is not None:
            entities["target"] = steps[0].target if steps and not unresolved else first.target
        probable_goal = first.goal or (steps[0].capability if steps else first.operation)

        if unresolved:
            missing = unresolved[0]
            described = f"{missing.operation} {missing.target}".strip() if missing.target else missing.operation
            return SemanticRequest(
                raw_text=raw_text,
                probable_goal=probable_goal,
                operation=first.operation,
                entities=entities,
                candidate_capabilities=[],
                confidence=0.0,
                ambiguity=["unresolved_capability"],
                clarification_question=f"I understood that you want me to {described}, but I don't have a way to do that yet.",
                validation_error="No registered capability matched the semantic intent.",
                steps=steps,
            )
        return SemanticRequest(
            raw_text=raw_text,
            probable_goal=probable_goal,
            operation=first.operation,
            entities=entities,
            candidate_capabilities=[step.capability for step in steps],
            confidence=0.95,
            steps=steps,
        )

    @staticmethod
    def _parse_json(response: Any) -> Dict[str, Any]:
        if not isinstance(response, str):
            raise SemanticInterpretationError("LLM semantic response was not text JSON.")
        text = response.strip()
        # Small models sometimes wrap JSON in a code fence or add a sentence around it.
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        if fenced:
            text = fenced.group(1)
        elif not text.startswith("{"):
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                text = text[start:end + 1]
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SemanticInterpretationError("LLM semantic response was malformed JSON.") from exc
        if not isinstance(payload, dict):
            raise SemanticInterpretationError("LLM semantic response must be a JSON object.")
        return payload

    @classmethod
    def _reject_unsafe_payload(cls, payload: Any) -> None:
        forbidden_keys = {"command", "shell", "script", "python", "code", "executable", "tool_call"}
        suspicious = re.compile(r"(?:subprocess|os\.system|powershell|cmd\.exe|python\s+-|&&|\|\||;)", re.I)

        def walk(value: Any, key: Optional[str] = None):
            if key and key.lower() in forbidden_keys:
                raise SemanticInterpretationError(f"Unsafe execution field '{key}' rejected.")
            if isinstance(value, dict):
                for child_key, child in value.items():
                    walk(child, str(child_key))
            elif isinstance(value, list):
                for child in value:
                    walk(child, key)
            elif isinstance(value, str) and suspicious.search(value):
                raise SemanticInterpretationError("Potential executable command content rejected.")

        walk(payload)


def default_semantic_interpreter() -> SemanticInterpreter:
    from app.cognition.llm.manager import RoleProvider
    from app.core.config import settings
    from app.router.registry import router_registry
    from app.tools.manager import tool_manager
    from app.presence.capability_manager import capability_manager

    provider = RoleProvider("understanding")  # follows the user's choice on every call
    catalog = CapabilityCatalog.from_sources(
        tool_registry=tool_manager.registry,
        router_registry=router_registry,
        capability_manager=capability_manager,
    )
    return SemanticInterpreter(provider=provider, catalog=catalog, timeout_seconds=settings.SEMANTIC_TIMEOUT_SECONDS)
