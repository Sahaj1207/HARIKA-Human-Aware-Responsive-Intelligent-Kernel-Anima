"""Spotify without its developer API: HARIKA uses the Spotify app the way a person would.

- Play anything: bring Spotify forward, check its search box has the keyboard focus
  (so keystrokes can't land anywhere else), type the request, press the best
  matching result's Play button.
- Liked songs: open the Liked Songs page (spotify:collection:tracks), press its Play.
- What's playing: the Spotify window's title, "Artist - Song" while music plays.
- Like this song: the player bar's "Add to Liked Songs" button.

Queueing a song and adding one to a playlist need Spotify connected: in the app they
live in a menu that search results only show on mouse hover, and HARIKA never takes
over the mouse.

Buttons and menu items are pressed through Windows UI Automation, the accessibility
interface screen readers use; the mouse is never moved. Every action is confirmed
(the title changes, or the button's name changes) or reported honestly as not done.

Used when Spotify isn't connected through its Web API (see spotify.py). Playback
happens wherever the user's Spotify is playing (Spotify's own behaviour).
"""
import asyncio
import ctypes
import logging
import os
import re
import time
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger("harika.tools.spotify_app")

_IDLE_TITLES = ("spotify", "spotify premium", "spotify free")
_SEARCH_BOX = "What do you want to play?"
_OPEN_WAIT = 12.0     # the app may need to start
_PAGE_WAIT = 12.0     # a page to show the button wanted (Spotify is sometimes slow to change page)
_PLAY_WAIT = 6.0      # the title to change once playing


class SpotifyAppError(RuntimeError):
    """Why it couldn't be done in the Spotify app (shown to the user)."""


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower())) - {"spotify", "song", "by", "the", "a", "and", "my"}


def is_playing(title: str) -> bool:
    return " - " in title and title.strip().lower() not in _IDLE_TITLES


def split_title(title: str) -> Tuple[str, str]:
    """'Imagine Dragons - Believer' -> ('Believer', 'Imagine Dragons')."""
    artist, _, song = title.partition(" - ")
    return song.strip(), artist.strip()


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


def installed() -> bool:
    from app.tools.system.installed_apps import installed_app_index
    return installed_app_index.find("spotify") is not None


class _Button:
    """A button as it was when read (Spotify rebuilds its page while results load)."""

    def __init__(self, control, name: str):
        self.control, self.Name = control, name


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


def _press(control) -> bool:
    """Press a button or menu item without moving the mouse."""
    import uiautomation as auto
    for pattern, action in ((auto.PatternId.InvokePattern, lambda p: p.Invoke()),
                            (auto.PatternId.ExpandCollapsePattern, lambda p: p.Expand()),
                            (auto.PatternId.LegacyIAccessiblePattern, lambda p: p.DoDefaultAction())):
        try:
            found = control.GetPattern(pattern)
            if found:
                action(found)
                return True
        except Exception:
            continue
    return False


def _wait_for(hwnd: int, pick: Callable[[List[_Button]], Optional[_Button]], timeout: float = _PAGE_WAIT) -> Optional[_Button]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = pick(_buttons(hwnd))
        if found is not None:
            return found
        time.sleep(0.5)
    return None


def _open_window() -> Tuple[int, str]:
    window = spotify_window()
    if window is None:
        os.startfile("spotify:")  # Spotify's own link: opens the app, nothing else
        deadline = time.monotonic() + _OPEN_WAIT
        while window is None and time.monotonic() < deadline:
            time.sleep(1.0)
            window = spotify_window()
    if window is None:
        raise SpotifyAppError("Spotify didn't open")
    return window


def _device(hwnd: int) -> str:
    name = next((b.Name for b in _buttons(hwnd) if b.Name.startswith("Playing on ")), "")
    return name.removeprefix("Playing on ").strip()


def _confirm_playing(before: str, expected: str = "") -> str:
    """The new "Artist - Song" title once playback starts, or ""."""
    deadline = time.monotonic() + _PLAY_WAIT
    while time.monotonic() < deadline:
        current = spotify_window()
        if current and is_playing(current[1]) and (current[1] != before or (expected and _words(expected) <= _words(current[1]))):
            return current[1]
        time.sleep(0.5)
    return ""


def _search(hwnd: int, query: str) -> None:
    """Type into Spotify's search box, only once it holds the keyboard focus."""
    import uiautomation as auto
    from app.tools.system import screen_reader
    from app.tools.system.device import bring_forward

    info = screen_reader._window_info(hwnd)
    if info is None or not bring_forward(info):
        raise SpotifyAppError("I couldn't bring Spotify to the front")
    box = next((c for c, _ in auto.WalkControl(auto.ControlFromHandle(hwnd), maxDepth=40)
                if c.ControlTypeName == "ComboBoxControl" and c.Name == _SEARCH_BOX), None)
    if box is None:
        raise SpotifyAppError("I couldn't find Spotify's search box")
    box.SetFocus()
    time.sleep(0.4)
    if auto.GetFocusedControl().Name != _SEARCH_BOX:
        raise SpotifyAppError("Spotify's search box didn't take the focus, so I didn't type anything")
    auto.SendKeys("{Ctrl}a", waitTime=0.1)
    auto.SendKeys(query.replace("{", "").replace("}", ""), interval=0.02, waitTime=0.1)


def _best_result(buttons: List[_Button], prefix: str, query: str) -> Optional[_Button]:
    """The search result button ("Play X", "More options for X") sharing most words with the request."""
    wanted = _words(query)
    scored = [(len(wanted & _words(b.Name[len(prefix):])), -i, b) for i, b in enumerate(buttons)
              if b.Name.startswith(prefix) and not b.Name.startswith("Playing on")]
    scored = [s for s in scored if s[0] > 0]
    return max(scored, key=lambda s: (s[0], s[1]))[2] if scored else None


def _player_like_button(buttons: List[_Button]) -> Optional[_Button]:
    """The player bar's like button: the one right before its Shuffle and Previous buttons."""
    names = [b.Name for b in buttons]
    for i in range(1, len(names) - 1):
        if names[i + 1] == "Previous" and "shuffle" in names[i].lower():
            return buttons[i - 1]
    return None


# ------------------------------------------------------------- actions (blocking)

def _with_uia(work):
    import uiautomation as auto
    with auto.UIAutomationInitializerInThread():
        return work()


def play_blocking(query: str) -> Tuple[str, str, str]:
    """Search and play the best match. Returns (now playing title, device, the result pressed)."""
    def work():
        hwnd, before = _open_window()
        _search(hwnd, query)
        target = _wait_for(hwnd, lambda bs: _best_result(bs, "Play ", query), timeout=6.0)
        if target is None:
            raise SpotifyAppError(f"I couldn't find {query} on Spotify")
        pressed = target.Name[5:]
        if not _press(target.control):
            raise SpotifyAppError(f"I found {pressed} in Spotify but couldn't start it. Press play there")
        return _confirm_playing(before, pressed), _device(hwnd), pressed
    return _with_uia(work)


def play_liked_blocking() -> Tuple[str, str]:
    def work():
        hwnd, before = _open_window()
        os.startfile("spotify:collection:tracks")  # Spotify's own link to Liked Songs
        target = _wait_for(hwnd, lambda bs: next((b for b in bs if b.Name == "Play Liked Songs"), None))
        if target is None or not _press(target.control):
            raise SpotifyAppError("I opened your Liked Songs but couldn't start them. Press play there")
        return _confirm_playing(before), _device(hwnd)
    return _with_uia(work)


def like_current_blocking() -> str:
    def work():
        window = spotify_window()
        if window is None or not is_playing(window[1]):
            raise SpotifyAppError("Nothing is playing on Spotify right now")
        song, artist = split_title(window[1])
        button = _wait_for(window[0], _player_like_button, timeout=4.0)
        if button is None:
            raise SpotifyAppError("I couldn't find Spotify's like button")
        if button.Name != "Add to Liked Songs":
            return f"{song} by {artist} is already in your liked songs."
        if not _press(button.control):
            raise SpotifyAppError("I couldn't press Spotify's like button")
        changed = _wait_for(window[0], lambda bs: (b := _player_like_button(bs)) and b.Name != "Add to Liked Songs" and b, timeout=3.0)
        if changed is None:
            raise SpotifyAppError("Spotify didn't confirm the like; check the heart in the player")
        return f"Saved {song} by {artist} to your liked songs."
    return _with_uia(work)


# ------------------------------------------------------------- what the tools call

def now_playing() -> Optional[Tuple[str, str]]:
    window = spotify_window()
    return split_title(window[1]) if window and is_playing(window[1]) else None


def _where(device: str) -> str:
    return f", on your {device}" if device else ""


async def play(query: str, kind: str = "track") -> Tuple[bool, str]:
    """(played, what to tell the user)."""
    if not installed():
        return False, ""
    try:
        title, device, pressed = await asyncio.to_thread(play_blocking, query)
    except SpotifyAppError as exc:
        return False, str(exc)
    if not title:
        return False, f"I pressed play on {pressed} but Spotify didn't start. Press play there"
    song, artist = split_title(title)
    return True, f"Playing {song} by {artist} on Spotify{_where(device)}."


async def play_liked() -> Tuple[bool, str]:
    try:
        title, device = await asyncio.to_thread(play_liked_blocking)
    except SpotifyAppError as exc:
        return False, str(exc)
    if not title:
        return False, "I pressed play on your Liked Songs but Spotify didn't start. Press play there"
    return True, f"Playing your liked songs on Spotify{_where(device)}."


async def run(blocking, *args) -> Tuple[bool, str]:
    try:
        return True, await asyncio.to_thread(blocking, *args)
    except SpotifyAppError as exc:
        return False, str(exc)
