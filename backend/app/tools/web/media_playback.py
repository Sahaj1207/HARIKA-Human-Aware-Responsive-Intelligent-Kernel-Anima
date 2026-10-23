import re
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional, Tuple

import httpx

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest


class MediaPlaybackTool(BaseTool):
    """Plays music or video by searching a media platform with a URL-encoded query."""

    manifest = ToolManifest(
        name="media_playback",
        display_name="Media Player",
        description="Plays songs, music or videos on YouTube (default) or Spotify.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="media",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["play_media"],
        operations={"play": "play_media"},
        ability="play music and videos on YouTube or Spotify",
        free_text_operations=["play"],
        target_description=("what to play, as a search query (e.g. 'relaxing music', 'believer by imagine dragons'); put the platform in "
                            "parameters.platform ('youtube' or 'spotify'); for Spotify, parameters.kind is 'artist', 'album' or 'playlist' "
                            "when the user asks for one of those rather than a song"),
    )
    timeout_seconds = 15.0

    PLATFORMS = ("youtube", "spotify")
    _VIDEO_ID = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Browser and URI handlers available", dependencies=["webbrowser", "httpx"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        query, _ = self._query_and_platform(args)
        if not query:
            return False, "Tell me what you'd like me to play."
        return True, None

    def _query_and_platform(self, args: Dict[str, Any]) -> Tuple[str, str]:
        target = str(args.get("target") or "").strip()
        query = str(args.get("search") or args.get("song") or "").strip()
        platform = str(args.get("platform") or "").strip().lower()
        # Models sometimes put the platform in target and the song in parameters.query.
        if target.lower() in self.PLATFORMS:
            platform = platform or target.lower()
            target = ""
        query = query or target
        if platform not in self.PLATFORMS:
            platform = "youtube"
        return query, platform

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        query, platform = self._query_and_platform(args)
        encoded = urllib.parse.quote(query)
        if dry_run:
            return {"dry_run": True, "action": "play_media", "query": query, "platform": platform}

        if platform == "spotify":
            from app.integrations.spotify import spotify_account
            kind = str(args.get("kind") or "track")
            if spotify_account.status()["connected"]:
                return await self._play_spotify_connected(query, kind)
            from app.tools.web import spotify_app
            if spotify_app.installed():
                # Not connected: HARIKA finds it and presses play in the Spotify app herself.
                played, message = await spotify_app.play(query, kind)
                return {"action": "play_media", "platform": "spotify", "query": query, "success": played,
                        "verified": played, "summary": message if played else None,
                        "error": None if played else message}
            return self._play_spotify(query, encoded)

        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        played_directly = False
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"Accept-Language": "en-US"}) as client:
                page = await client.get(url)
            match = self._VIDEO_ID.search(page.text)
            if match:
                url = f"https://www.youtube.com/watch?v={match.group(1)}"
                played_directly = True
        except Exception:
            pass  # fall back to the results page

        opened = webbrowser.open(url)
        summary = (
            f"Playing {query} on YouTube." if played_directly
            else f"I opened YouTube results for {query}; pick the one you want."
        )
        return {
            "action": "play_media",
            "platform": "youtube",
            "query": query,
            "url": url,
            "success": bool(opened),
            "verified": bool(opened),
            "summary": summary if opened else None,
            "error": None if opened else "the browser could not be opened",
        }

    async def _play_spotify_connected(self, query: str, kind: str) -> Dict[str, Any]:
        """Starts playback through Spotify's Web API (the account is connected in Settings)."""
        from app.integrations.spotify import SpotifyError, SpotifyNotConnected
        from app.tools.web.spotify_tool import explain, spotify_player

        try:
            summary = await spotify_player.play_search(query, kind)
        except (SpotifyNotConnected, SpotifyError) as exc:
            return {"action": "play_media", "platform": "spotify", "query": query, "success": False,
                    "verified": False, "error": explain(exc)}
        return {"action": "play_media", "platform": "spotify", "query": query, "success": True, "verified": True,
                "summary": summary, "error": None}

    def _play_spotify(self, query: str, encoded: str) -> Dict[str, Any]:
        from app.tools.system.installed_apps import installed_app_index

        if installed_app_index.find("spotify") is not None:
            uri = f"spotify:search:{encoded}"
            opened = webbrowser.open(uri)
            where = "the Spotify app"
        else:
            uri = f"https://open.spotify.com/search/{encoded}"
            opened = webbrowser.open(uri)
            where = "Spotify on the web"
        return {
            "action": "play_media",
            "platform": "spotify",
            "query": query,
            "url": uri,
            "success": bool(opened),
            "verified": bool(opened),
            # Spotify only exposes search via URI; starting playback needs its Web API.
            "summary": f"I searched {where} for {query}. Hit play on the top result." if opened else None,
            "error": None if opened else "Spotify could not be opened",
        }


media_playback_tool = MediaPlaybackTool()
tool_registry.register_tool(media_playback_tool)
