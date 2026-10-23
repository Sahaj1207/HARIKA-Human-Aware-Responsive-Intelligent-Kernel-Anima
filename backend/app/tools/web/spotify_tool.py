"""Spotify, with the account connected: "play my liked songs", "play my workout playlist", "what's playing?",
"like this song", "add this to my road trip playlist", "play Believer next".

"Play X on Spotify" itself stays with the media tool, which uses play_search() here
when Spotify is connected. Playback goes to the device already playing, else this
computer's Spotify app (opened if needed). Controlling playback needs Premium.
"""
import asyncio
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.spotify import SpotifyError, SpotifyNotConnected, spotify_account
from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

logger = logging.getLogger("harika.tools.spotify")

LIKED = "liked songs"
_KINDS = ("track", "artist", "album", "playlist")
_DEVICE_WAIT = 10.0


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower())) - {"my", "the", "a", "playlist", "songs", "song"}


def _best(items: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    """The item whose name shares most words with the query (Spotify's order breaks ties)."""
    wanted = _words(query)
    scored = [(len(wanted & _words(item.get("name", ""))), -i, item) for i, item in enumerate(items) if item]
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return scored[0][2] if scored and (scored[0][0] or not wanted) else None


def _track_label(track: Dict[str, Any]) -> str:
    artists = ", ".join(a["name"] for a in track.get("artists", [])[:2])
    return f"{track.get('name', 'that')}" + (f" by {artists}" if artists else "")


class SpotifyPlayer:
    def __init__(self, account=spotify_account):
        self.account = account

    async def device(self) -> str:
        """The device to play on: the active one, else this computer (starting the Spotify app if needed)."""
        devices = (await self.account.request("GET", "/me/player/devices") or {}).get("devices", [])
        chosen = next((d for d in devices if d.get("is_active")), None) or next(
            (d for d in devices if d.get("type") == "Computer"), None) or (devices[0] if devices else None)
        if chosen:
            return chosen["id"]
        from app.tools.system.installed_apps import installed_app_index
        if installed_app_index.find("spotify") is None or not hasattr(os, "startfile"):
            raise SpotifyError("Open Spotify on your phone or computer first, then ask again")
        os.startfile("spotify:")  # the Spotify app registers this link; it opens the app, nothing else
        waited = 0.0
        while waited < _DEVICE_WAIT:
            await asyncio.sleep(1.0)
            waited += 1.0
            devices = (await self.account.request("GET", "/me/player/devices") or {}).get("devices", [])
            if devices:
                return devices[0]["id"]
        raise SpotifyError("Spotify is opening; ask me again in a moment")

    async def _play(self, body: Dict[str, Any]) -> None:
        device = await self.device()
        await self.account.request("PUT", f"/me/player/play?device_id={device}", json=body)

    async def play_search(self, query: str, kind: str = "track") -> str:
        kind = kind if kind in _KINDS else "track"
        found = await self.account.request("GET", "/search", params={"q": query, "type": kind, "limit": 5})
        items = (found or {}).get(f"{kind}s", {}).get("items", [])
        item = items[0] if kind == "track" and items else _best(items, query)
        if not item:
            raise SpotifyError(f"I couldn't find {query} on Spotify")
        if kind == "track":
            await self._play({"uris": [item["uri"]]})
            return f"Playing {_track_label(item)} on Spotify."
        await self._play({"context_uri": item["uri"]})
        return f"Playing {item['name']} on Spotify."

    async def play_library(self, name: str) -> str:
        if not _words(name) or name.strip().lower() == LIKED:
            saved = await self.account.request("GET", "/me/tracks", params={"limit": 50})
            uris = [entry["track"]["uri"] for entry in (saved or {}).get("items", []) if entry.get("track")]
            if not uris:
                raise SpotifyError("You don't have any liked songs on Spotify yet")
            random.shuffle(uris)
            await self._play({"uris": uris})
            return "Playing your liked songs on Spotify, shuffled."
        playlist = await self.find_playlist(name)
        if playlist is None:
            return await self.play_search(name, "playlist")  # not one of theirs: a public playlist
        await self._play({"context_uri": playlist["uri"]})
        return f"Playing your {playlist['name']} playlist on Spotify."

    async def find_playlist(self, name: str) -> Optional[Dict[str, Any]]:
        playlists, offset = [], 0
        while offset < 200:
            page = await self.account.request("GET", "/me/playlists", params={"limit": 50, "offset": offset}) or {}
            playlists += [p for p in page.get("items", []) if p]
            if not page.get("next"):
                break
            offset += 50
        return _best(playlists, name)

    async def now_playing(self) -> Tuple[Optional[Dict[str, Any]], bool]:
        current = await self.account.request("GET", "/me/player/currently-playing")
        if not current or not current.get("item"):
            return None, False
        return current["item"], bool(current.get("is_playing"))

    async def like_current(self) -> str:
        track, _ = await self.now_playing()
        if track is None:
            raise SpotifyError("Nothing is playing on Spotify right now")
        await self.account.request("PUT", "/me/tracks", params={"ids": track["id"]})
        return f"Saved {_track_label(track)} to your liked songs."

    async def add_current_to(self, name: str) -> str:
        track, _ = await self.now_playing()
        if track is None:
            raise SpotifyError("Nothing is playing on Spotify right now")
        playlist = await self.find_playlist(name)
        if playlist is None:
            raise SpotifyError(f"I couldn't find a playlist of yours called {name}")
        await self.account.request("POST", f"/playlists/{playlist['id']}/tracks", json={"uris": [track["uri"]]})
        return f"Added {_track_label(track)} to {playlist['name']}."

    async def queue(self, query: str) -> str:
        found = await self.account.request("GET", "/search", params={"q": query, "type": "track", "limit": 1})
        items = (found or {}).get("tracks", {}).get("items", [])
        if not items:
            raise SpotifyError(f"I couldn't find {query} on Spotify")
        device = await self.device()
        await self.account.request("POST", "/me/player/queue", params={"uri": items[0]["uri"], "device_id": device})
        return f"{_track_label(items[0])} is up next."


spotify_player = SpotifyPlayer()


def explain(exc: Exception) -> str:
    text = str(exc)
    if text == "NO_ACTIVE_DEVICE":
        return "Spotify isn't open on any device. Open it on your phone or computer, then ask again"
    return text


class SpotifyTool(BaseTool):
    manifest = ToolManifest(
        name="spotify",
        display_name="Spotify",
        description="With Spotify connected: plays your liked songs or playlists, says what's playing, likes the current song, adds it to a playlist, queues songs.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="media",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["spotify_library", "spotify_now_playing", "spotify_like", "spotify_add_to_playlist", "spotify_queue"],
        operations={"play_library": "spotify_library", "now_playing": "spotify_now_playing", "like_song": "spotify_like",
                    "add_to_playlist_spotify": "spotify_add_to_playlist", "queue_song": "spotify_queue"},
        free_text_operations=["play_library", "add_to_playlist_spotify", "queue_song"],
        default_targets={"now_playing": "spotify", "like_song": "current song", "play_library": LIKED},
        ability="play your Spotify liked songs and playlists, say what's playing, like songs, add them to playlists and queue them",
        target_description=(
            "for play_library: 'liked songs' or the name of one of the user's playlists; for add_to_playlist_spotify: "
            "the playlist's name (the song is the one playing); for queue_song: the song to play next"
        ),
    )
    timeout_seconds = 30.0

    def __init__(self, player: SpotifyPlayer = spotify_player):
        self.player = player

    def health_check(self) -> ToolHealth:
        status = spotify_account.status()
        return ToolHealth(available=True, reason="Connected" if status["connected"] else "Connect in Settings > Accounts",
                          dependencies=["httpx"])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        return (text or self.manifest.default_targets.get(operation or "", "")), 0.8

    def describe_action(self, args: Dict[str, Any]) -> str:
        operation, target = args.get("operation"), args.get("target")
        return {"play_library": f"play {target} on Spotify", "now_playing": "check what's playing",
                "like_song": "like this song", "add_to_playlist_spotify": f"add this song to {target}",
                "queue_song": f"queue {target}"}.get(operation, "use Spotify")

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        operation, target = args.get("operation"), str(args.get("target") or "").strip()
        if dry_run:
            return {"dry_run": True, "action": operation, "target": target}
        try:
            if operation == "now_playing":
                track, playing = await self.player.now_playing()
                summary = "Nothing is playing on Spotify right now." if track is None else (
                    f"{'Playing' if playing else 'Paused on'} {_track_label(track)}"
                    + (f", from {track['album']['name']}." if track.get("album", {}).get("name") else "."))
            elif operation == "like_song":
                summary = await self.player.like_current()
            elif operation == "add_to_playlist_spotify":
                summary = await self.player.add_current_to(target)
            elif operation == "queue_song":
                summary = await self.player.queue(target)
            else:
                summary = await self.player.play_library(target or LIKED)
        except (SpotifyNotConnected, SpotifyError) as exc:
            return {"success": False, "verified": False, "error": explain(exc)}
        return {"action": operation, "success": True, "verified": True, "summary": summary, "error": None}


spotify_tool = SpotifyTool()
tool_registry.register_tool(spotify_tool)
