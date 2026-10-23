"""Playing on Spotify without its developer API, the way a person would.

1. Find the exact Spotify page with a web search (every song, artist, album and
   playlist has a public open.spotify.com link).
2. Open it in the Spotify app through its own link scheme (spotify:track:...).
3. Press Play on that page through Windows UI Automation, the accessibility
   interface screen readers use: the song's own row ("Play Believer by Imagine
   Dragons") or the page's main Play button.
4. Confirm from the Spotify window's title, which becomes "Artist - Song" while
   music plays. If it doesn't change, HARIKA says so instead of claiming success.

When the web search finds nothing, HARIKA uses Spotify's own search box instead:
it brings Spotify forward, checks that the search box has the keyboard focus (so
keystrokes can't land anywhere else), types the request, and presses the best
matching result's Play button.

Used when Spotify isn't connected through its Web API (see spotify.py). Playback
happens wherever the user's Spotify is playing (Spotify's own behaviour).
"""
import asyncio
import ctypes
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("harika.tools.spotify_app")

_LINK = re.compile(r"https://open\.spotify\.com/(?:intl-[a-z]+/)?(track|artist|album|playlist)/([A-Za-z0-9]{22})")
_IDLE_TITLES = ("spotify", "spotify premium", "spotify free")
_OPEN_WAIT = 12.0     # the app may need to start
_PAGE_WAIT = 6.0      # the page to show its buttons
_PLAY_WAIT = 6.0      # the title to change once playing


@dataclass
class Found:
    kind: str           # track, artist, album or playlist
    uri: str            # spotify:track:<id>
    name: str           # "Believer"
    by: str             # "Imagine Dragons" (songs and albums)


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower())) - {"spotify", "song", "by", "the", "a", "and", "lyrics"}


def parse_title(title: str) -> Tuple[str, str]:
    """'Believer - song and lyrics by Imagine Dragons | Spotify' -> ('Believer', 'Imagine Dragons')."""
    title = re.sub(r"\s*\|\s*Spotify.*$", "", title or "").strip()
    match = re.match(r"(.+?)\s+-\s+(?:song|album|single|ep|playlist)(?: and lyrics)? by (.+)$", title, re.I)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return re.sub(r"\s+-\s+.*$", "", title).strip(), ""


def choose(results: List[dict], query: str, kind: str) -> Optional[Found]:
    """The search result that is a Spotify page of the wanted kind and best matches the request."""
    wanted = _words(query)
    best, best_score = None, -1.0
    for rank, result in enumerate(results):
        match = _LINK.search(result.get("url", ""))
        if not match:
            continue
        found_kind, ident = match.groups()
        name, by = parse_title(result.get("title", ""))
        overlap = len(wanted & _words(f"{name} {by}")) / max(len(wanted), 1)
        score = overlap + (0.5 if found_kind == kind else 0.0) - rank * 0.02
        if score > best_score:
            best, best_score = Found(found_kind, f"spotify:{found_kind}:{ident}", name, by), score
    return best if best is not None and best_score >= 0.5 else None


async def find(query: str, kind: str = "track") -> Optional[Found]:
    from app.tools.web.sources import search

    words = f"{query} spotify" + (f" {kind}" if kind in ("artist", "album", "playlist") else "")
    # No retry: when the search engine is busy, Spotify's own search box is quicker than waiting.
    return choose(await search(words, 8), query, kind)


# ------------------------------------------------------------- the Spotify window

def spotify_window():
    """(hwnd, title) of Spotify's main window, or None."""
    from app.tools.system import screen_reader

    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            info = screen_reader._window_info(hwnd)
            if info and info.process == "spotify.exe" and info.title:
                found.append((info.hwnd, info.title))
        return True

    ctypes.windll.user32.EnumWindows(visit, 0)
    return found[0] if found else None


def is_playing(title: str) -> bool:
    return " - " in title and title.strip().lower() not in _IDLE_TITLES


class _Button:
    """A button as it was when read (Spotify rebuilds its page while results load)."""

    def __init__(self, control, name: str):
        self.control, self.Name = control, name

    def GetInvokePattern(self):
        return self.control.GetInvokePattern()


def _buttons(hwnd: int) -> List[_Button]:
    import uiautomation as auto
    out = []
    try:
        for control, _ in auto.WalkControl(auto.ControlFromHandle(hwnd), maxDepth=40):
            try:
                if control.ControlTypeName == "ButtonControl" and control.Name:
                    out.append(_Button(control, control.Name))
            except Exception:
                continue  # this element went away while being read
    except Exception as exc:
        logger.info(f"[SpotifyApp] Reading Spotify's buttons stopped early: {exc}")
    return out


def _press_play(hwnd: int, found: Found) -> Tuple[bool, str]:
    """Presses the right Play button on the open page. Returns (pressed, where it plays)."""
    import uiautomation as auto

    with auto.UIAutomationInitializerInThread():
        deadline = time.monotonic() + _PAGE_WAIT
        target = None
        while time.monotonic() < deadline and target is None:
            buttons = _buttons(hwnd)
            names = [b.Name for b in buttons]
            if found.kind == "track":
                # The song's own row: "Play Believer by Imagine Dragons".
                want = f"play {found.name} by".lower()
                target = next((b for b in buttons if b.Name.lower().startswith(want)), None)
            if target is None and (found.kind != "track" or time.monotonic() > deadline - 2):
                # The page's main Play button; the player bar's Play sits right after "Previous".
                for i, name in enumerate(names):
                    if name == "Play" and (i == 0 or names[i - 1] != "Previous"):
                        target = buttons[i]
                        break
            if target is None:
                time.sleep(0.5)
        device = next((b.Name for b in _buttons(hwnd) if b.Name.startswith("Playing on ")), "")
        if target is None:
            return False, device
        try:
            target.GetInvokePattern().Invoke()
        except Exception as exc:
            logger.info(f"[SpotifyApp] Couldn't press Play: {exc}")
            return False, device
        return True, device


def _open_and_play(found: Found) -> Tuple[str, str]:
    """Blocking: open the page, press play, wait for the title. Returns (now playing title or "", device)."""
    before = (spotify_window() or (0, ""))[1]
    os.startfile(found.uri)  # Spotify's own link scheme; opens the page in the app, nothing else
    window, waited = spotify_window(), 0.0
    while window is None and waited < _OPEN_WAIT:
        time.sleep(1.0)
        waited += 1.0
        window = spotify_window()
    if window is None:
        return "", ""
    time.sleep(1.5)  # let the page change before reading its buttons
    pressed, device = _press_play(window[0], found)
    if not pressed:
        return "", device
    deadline = time.monotonic() + _PLAY_WAIT
    while time.monotonic() < deadline:
        current = spotify_window()
        # Playing, and not just what was already playing before (unless it's the very song asked for).
        if current and is_playing(current[1]) and (current[1] != before or _words(found.name) <= _words(current[1])):
            return current[1], device
        time.sleep(0.5)
    return "", device


_SEARCH_BOX = "What do you want to play?"


def _search_in_app(query: str) -> Tuple[str, str, str]:
    """Blocking: type the request into Spotify's search and play the best result.
    Returns (now playing title or "", device, the result pressed)."""
    import uiautomation as auto
    from app.tools.system import screen_reader
    from app.tools.system.device import bring_forward

    window = spotify_window()
    if window is None:
        os.startfile("spotify:")
        for _ in range(int(_OPEN_WAIT)):
            time.sleep(1.0)
            window = spotify_window()
            if window:
                break
    if window is None:
        return "", "", ""
    before = window[1]
    info = screen_reader._window_info(window[0])
    if info is None or not bring_forward(info):
        return "", "", ""
    with auto.UIAutomationInitializerInThread():
        root = auto.ControlFromHandle(window[0])
        box = next((c for c, _ in auto.WalkControl(root, maxDepth=40)
                    if c.ControlTypeName == "ComboBoxControl" and c.Name == _SEARCH_BOX), None)
        if box is None:
            return "", "", ""
        box.SetFocus()
        time.sleep(0.4)
        if auto.GetFocusedControl().Name != _SEARCH_BOX:
            return "", "", ""  # never type unless Spotify's search box has the focus
        auto.SendKeys("{Ctrl}a", waitTime=0.1)
        auto.SendKeys(query.replace("{", "").replace("}", ""), interval=0.02, waitTime=0.1)
        wanted, target, deadline = _words(query), None, time.monotonic() + _PAGE_WAIT
        while target is None and time.monotonic() < deadline:
            time.sleep(0.6)
            results = [b for b in _buttons(window[0]) if b.Name.startswith("Play ") and not b.Name.startswith("Playing on")]
            scored = [(len(wanted & _words(b.Name[5:])), -i, b) for i, b in enumerate(results)]
            scored = [s for s in scored if s[0] > 0]
            if scored:
                target = max(scored, key=lambda s: (s[0], s[1]))[2]
        device = next((b.Name for b in _buttons(window[0]) if b.Name.startswith("Playing on ")), "")
        if target is None:
            return "", device, ""
        pressed = target.Name[5:]
        try:
            target.GetInvokePattern().Invoke()
        except Exception:
            return "", device, pressed
    deadline = time.monotonic() + _PLAY_WAIT
    while time.monotonic() < deadline:
        current = spotify_window()
        if current and is_playing(current[1]) and current[1] != before:
            return current[1], device, pressed
        time.sleep(0.5)
    return "", device, pressed


def installed() -> bool:
    from app.tools.system.installed_apps import installed_app_index
    return installed_app_index.find("spotify") is not None


async def play(query: str, kind: str = "track") -> Tuple[bool, str]:
    """(played, what to tell the user)."""
    if not installed():
        return False, ""
    found = await find(query, kind)
    if found is None:
        # The web didn't find it: search inside Spotify itself.
        title, device, pressed = await asyncio.to_thread(_search_in_app, query)
        where = f", on your {device.removeprefix('Playing on ').strip()}" if device else ""
        if title:
            return True, f"Playing {title.split(' - ', 1)[-1]} by {title.split(' - ', 1)[0]} on Spotify{where}."
        if pressed:
            return False, f"I found {pressed} in Spotify but couldn't start it. Press play there"
        return False, f"I couldn't find {query} on Spotify"
    title, device = await asyncio.to_thread(_open_and_play, found)
    label = f"{found.name} by {found.by}" if found.by and found.kind in ("track", "album") else found.name
    if not title:
        return False, f"I opened {label} in Spotify but couldn't start it. Press play there"
    where = f", on your {device.removeprefix('Playing on ').strip()}" if device else ""
    if found.kind == "track" and not (_words(found.name) & _words(title)):
        return True, f"Spotify is playing {title.split(' - ', 1)[-1]}{where}, not exactly {label}."
    return True, f"Playing {label} on Spotify{where}."
