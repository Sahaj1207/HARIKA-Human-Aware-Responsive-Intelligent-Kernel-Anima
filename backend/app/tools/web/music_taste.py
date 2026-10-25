"""Music that fits the user: "play something I'd like", "put on something for coding",
"what kind of music do I like?".

The taste profile comes from what they play on this computer (memory/listening.py).
The conversation model only chooses what to search for, as JSON that is checked here;
the existing media player (Spotify or YouTube) plays it.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.memory.listening import ListeningLog, listening_log
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

logger = logging.getLogger("harika.tools.music_taste")

ANYTHING = "anything"
_PROMPT = """You pick music for HARIKA's user. Choose ONE thing to search for that fits their taste and the moment.
Their listening on this computer:
{profile}

It is {part} now. Prefer artists and styles they already play (most of the time), now and then something close
to them. Reply with STRICT JSON only: {{"query": "<artist and song, or a mix like 'arijit singh evening mix'>",
"why": "<one short friendly sentence, spoken to them, why this fits>"}}"""


class MusicTasteTool(BaseTool):
    manifest = ToolManifest(
        name="music_taste",
        display_name="Music for you",
        description="Plays music that fits the user's taste and the moment, learned from what they listen to on this computer.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="media",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["recommend_media", "describe_taste"],
        operations={"play_for_me": "recommend_media", "music_taste": "describe_taste"},
        free_text_operations=["play_for_me", "music_taste"],
        default_targets={"play_for_me": ANYTHING, "music_taste": "me"},
        ability="pick music you'll like for the moment (I learn what you listen to)",
        target_description=(
            "for play_for_me: the mood or moment in plain words ('coding', 'late night', 'workout', 'relaxing'), "
            "or 'anything' when they just want something they'll like; parameters.platform ('spotify' or 'youtube') "
            "only when they name one. music_taste is a question about what music they like"
        ),
    )
    timeout_seconds = 30.0

    def __init__(self, log: ListeningLog = listening_log):
        super().__init__()
        self.log = log

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Uses your listening on this computer and the media player")

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        return (requested or ANYTHING).strip(), 0.8

    def describe_action(self, args: Dict[str, Any]) -> str:
        return "tell you what music you like" if args.get("operation") == "music_taste" else "play something you'll like"

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        profile = self.log.profile(datetime.now())
        if args.get("operation") == "music_taste":
            return {"action": "describe_taste", "success": True, "verified": True, "summary": self.taste_summary(profile)}
        moment = str(args.get("target") or "").strip()
        moment = "" if moment.lower() in (ANYTHING, "something", "music") else moment
        query, why = await self.choose(profile, moment)
        platform = self.platform(profile, str(args.get("platform") or ""))
        if dry_run:
            return {"dry_run": True, "action": "recommend_media", "query": query, "platform": platform}
        from app.tools.web.media_playback import media_playback_tool
        played = await media_playback_tool.execute({"target": query, "platform": platform})
        if played.get("success") and why:
            played["summary"] = f"{why} {played.get('summary') or ''}".strip()
        return {**played, "action": "recommend_media", "query": query}

    # ------------------------------------------------------------- choosing

    async def choose(self, profile: dict, moment: str) -> Tuple[str, str]:
        """(search query, why it fits): the model's pick if it gives a usable one, else a simple one."""
        from app.cognition.llm.manager import RoleProvider

        system = _PROMPT.format(profile=ListeningLog.describe(profile), part=profile["now_part"])
        ask = f"Something for: {moment}" if moment else "Something I'd like right now."
        try:
            result = await RoleProvider("conversation").generate_response([{"role": "user", "content": ask}], system,
                                                                           json_mode=True)
            picked = self._parse(result.get("response", "")) if not result.get("error") else None
        except Exception as exc:
            logger.info(f"[Music] Picking without the model: {exc}")
            picked = None
        return picked or self.simple_pick(profile, moment)

    @staticmethod
    def _parse(text: str) -> Optional[Tuple[str, str]]:
        match = re.search(r"\{.*\}", text or "", re.S)
        try:
            data = json.loads(match.group(0)) if match else {}
        except ValueError:
            return None
        query = str(data.get("query") or "").strip()
        why = str(data.get("why") or "").strip()
        if not query or len(query) > 80 or "://" in query:
            return None
        return query, why[:200]

    @staticmethod
    def simple_pick(profile: dict, moment: str) -> Tuple[str, str]:
        now_artists = profile["by_time_of_day"].get(profile["now_part"]) or profile["top_artists"]
        if now_artists:
            artist = now_artists[0]
            return (f"{artist} {moment} mix" if moment else f"{artist} mix"), f"You've been playing a lot of {artist}."
        return (f"{moment} music mix" if moment else "chill music mix"), ""

    @staticmethod
    def platform(profile: dict, asked: str) -> str:
        if asked.lower() in ("spotify", "youtube"):
            return asked.lower()
        return "spotify" if profile["apps"][:1] == ["Spotify"] else "youtube"

    def taste_summary(self, profile: dict) -> str:
        if not profile["plays"]:
            if not self.log.learning():
                return "I'm not learning what you listen to; you can turn it on in Settings > Memory."
            return ("I haven't heard you play much yet. I learn as you listen in Spotify, YouTube and other players, "
                    "so ask me again in a few days.")
        top = profile["top_artists"]
        text = f"Lately you play a lot of {', '.join(top[:3])}" if top else "You play a mix of things"
        part = profile["by_time_of_day"]
        evening = part.get("evening") or part.get("night")
        if evening and evening[0] not in top[:1]:
            text += f", and {evening[0]} in the evenings"
        where = f", mostly in {profile['apps'][0]}" if profile["apps"] else ""
        return f"{text}{where}."


music_taste_tool = MusicTasteTool()
tool_registry.register_tool(music_taste_tool)
