"""What the user listens to on this computer, so "play something I'd like" fits them.

Windows tells apps what is playing in Spotify, a browser tab (YouTube) and other players
(the same information as the media controls in the volume flyout). Every 20 seconds
HARIKA looks at what is playing; a track counts once it has played for 30 seconds, and
only its title, artist (or channel), app and when it played are kept, in this computer's
HARIKA data folder. Nothing is kept while "Learn what I listen to" is off, and the
history can be forgotten in Settings > Memory.
"""
import asyncio
import json
import logging
import platform
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.paths import data_path

logger = logging.getLogger("harika.memory.listening")

SAMPLE_SECONDS = 20
COUNTS_AFTER_SECONDS = 30
KEEP_DAYS = 120
_PLAYING = 4  # GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING
_APP_NAMES = {"msedge": "Edge", "chrome": "Chrome", "firefox": "Firefox", "spotify": "Spotify",
              "zunemusic": "Media Player", "brave": "Brave", "opera": "Opera"}


@dataclass
class MediaNow:
    app: str
    title: str
    artist: str
    playing: bool
    position: float = 0.0  # seconds into the track or video
    duration: float = 0.0

    @property
    def in_browser(self) -> bool:
        return self.app in ("Edge", "Chrome", "Firefox", "Brave", "Opera")


def app_name(app_id: str) -> str:
    """'Spotify.exe' -> 'Spotify'; 'Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic' -> 'Media Player'."""
    base = (app_id or "").split("!")[0].split("_")[0]
    base = base[:-4] if base.lower().endswith(".exe") else base
    last = base.split(".")[-1] if "." in base else base
    return _APP_NAMES.get(last.lower(), last or "an app")


async def media_sessions() -> List[MediaNow]:
    """What media apps report right now ([] when nothing does, or off Windows)."""
    if platform.system() != "Windows":
        return []
    from app.core.native import load_in_safe_order
    load_in_safe_order()  # WinRT loaded before onnxruntime crashes the process
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
    except ImportError:
        return []
    manager = await Manager.request_async()
    found = []
    for session in manager.get_sessions():
        try:
            props = await session.try_get_media_properties_async()
            timeline = session.get_timeline_properties()
            found.append(MediaNow(
                app=app_name(session.source_app_user_model_id),
                title=(props.title or "").strip(),
                artist=(props.artist or "").strip(),
                playing=int(session.get_playback_info().playback_status) == _PLAYING,
                position=timeline.position.total_seconds() if timeline.position else 0.0,
                duration=timeline.end_time.total_seconds() if timeline.end_time else 0.0,
            ))
        except Exception as exc:  # one app's odd session shouldn't hide the others
            logger.debug(f"[Listening] Skipped a media session: {exc}")
    return [m for m in found if m.title]


def _part_of_day(hour: int) -> str:
    if hour < 5:
        return "late night"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 21:
        return "evening"
    return "night"


class ListeningLog:
    def __init__(self, path: Optional[Path] = None, settings_path: Optional[Path] = None):
        self.path = path or data_path("memory", "listening.json")
        self.settings_path = settings_path or data_path("settings", "listening.json")
        self._lock = threading.Lock()
        self._current: Dict[Tuple[str, str, str], List[float]] = {}  # track -> [first seen, seconds heard]

    # ------------------------------------------------------------- on / off

    def learning(self) -> bool:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8")).get("learn", True) is not False
        except (OSError, ValueError):
            return True

    def set_learning(self, on: bool) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps({"learn": bool(on)}), encoding="utf-8")
        if not on:
            self._current.clear()

    # ------------------------------------------------------------- plays

    def plays(self, days: int = KEEP_DAYS) -> List[dict]:
        try:
            plays = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        since = (datetime.now() - timedelta(days=days)).isoformat()
        return [p for p in plays if p.get("time", "") >= since]

    def record(self, title: str, artist: str, app: str, seconds: float, when: datetime) -> None:
        with self._lock:
            plays = self.plays() + [{"title": title, "artist": artist, "app": app,
                                     "seconds": int(seconds), "time": when.isoformat(timespec="seconds")}]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(plays[-5000:], ensure_ascii=False), encoding="utf-8")

    def forget(self) -> None:
        with self._lock:
            self._current.clear()
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def observe(self, sessions: List[MediaNow], elapsed: float, now: Optional[datetime] = None) -> None:
        """One look at what's playing: adds `elapsed` seconds to each playing track, and records a
        track that stopped or changed if it was heard long enough."""
        if not self.learning():
            return
        now = now or datetime.now()
        playing = {(m.app, m.title, m.artist) for m in sessions if m.playing}
        for track in playing:
            first, heard = self._current.get(track, [time.time(), 0.0])
            self._current[track] = [first, heard + elapsed]
        for track in [t for t in self._current if t not in playing]:
            first, heard = self._current.pop(track)
            if heard >= COUNTS_AFTER_SECONDS:
                app, title, artist = track
                self.record(title, artist, app, heard, now - timedelta(seconds=heard))

    # ------------------------------------------------------------- taste

    def profile(self, now: Optional[datetime] = None, days: int = 60) -> dict:
        """What they play most, overall and by time of day, and where."""
        now = now or datetime.now()
        plays = self.plays(days)
        by_artist: Counter = Counter()
        by_app: Counter = Counter()
        by_part: Dict[str, Counter] = {}
        for p in plays:
            who = p.get("artist") or ""
            seconds = p.get("seconds", 0)
            by_app[p.get("app", "")] += seconds
            if who:
                by_artist[who] += seconds
                by_part.setdefault(_part_of_day(datetime.fromisoformat(p["time"]).hour), Counter())[who] += seconds
        return {
            "plays": len(plays),
            "hours": round(sum(p.get("seconds", 0) for p in plays) / 3600, 1),
            "top_artists": [a for a, _ in by_artist.most_common(8)],
            "by_time_of_day": {part: [a for a, _ in c.most_common(3)] for part, c in by_part.items()},
            "apps": [a for a, _ in by_app.most_common(3) if a],
            "recent": [f"{p['title']} ({p['artist']})" if p.get("artist") else p["title"] for p in plays[-8:]][::-1],
            "now_part": _part_of_day(now.hour),
        }

    @staticmethod
    def describe(profile: dict) -> str:
        """The profile in a few plain lines (for the model choosing music)."""
        if not profile["plays"]:
            return "Nothing heard yet."
        lines = [f"Most played (last 60 days): {', '.join(profile['top_artists']) or 'unknown artists'}."]
        for part, artists in profile["by_time_of_day"].items():
            lines.append(f"In the {part}: {', '.join(artists)}.")
        if profile["apps"]:
            lines.append(f"Plays music in: {', '.join(profile['apps'])}.")
        if profile["recent"]:
            lines.append(f"Recently: {'; '.join(profile['recent'][:5])}.")
        return "\n".join(lines)


listening_log = ListeningLog()


async def run_listening_loop(log: ListeningLog = listening_log, interval: float = SAMPLE_SECONDS) -> None:
    """Notes what's playing every `interval` seconds while learning is on."""
    if platform.system() != "Windows":
        return
    while True:
        await asyncio.sleep(interval)
        if not log.learning():
            continue
        try:
            log.observe(await media_sessions(), interval)
        except Exception as exc:
            logger.debug(f"[Listening] Couldn't check what's playing: {exc}")
