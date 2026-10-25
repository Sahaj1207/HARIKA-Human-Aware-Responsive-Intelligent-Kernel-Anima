"""Browsers HARIKA can do website tasks in. Each driver offers the same few actions, all built on
page.js: open a page, look at it, click, type, choose, scroll, go back.

- EdgeWindow: HARIKA's own Edge (or Chrome) window, with its own profile in HARIKA's data
  folder, driven through the browser's DevTools connection on this computer. Started only
  for a website task; sign-ins made there stay there.
- The extension driver (extension_bridge.py) does the same in a tab of the user's own
  Chrome or Edge.
"""
import asyncio
import json
import logging
import os
import platform
import subprocess
import time
from itertools import count
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.paths import data_path

logger = logging.getLogger("harika.tools.browser")

PAGE_SCRIPT = (Path(__file__).with_name("page.js")).read_text(encoding="utf-8")


class BrowserUnavailable(RuntimeError):
    """The browser couldn't be started or reached."""


class PageError(RuntimeError):
    """An action failed on the page (the element went away, the page refused...)."""


class BrowserDriver:
    name = "browser"

    async def start(self) -> None: ...
    async def open(self, url: str) -> None: ...
    async def snapshot(self) -> Dict[str, Any]: ...
    async def click(self, element_id: int) -> None: ...
    async def type(self, element_id: int, text: str) -> None: ...
    async def press_enter(self, element_id: int) -> None: ...
    async def choose(self, element_id: int, option: str) -> str: ...
    async def scroll(self, direction: str) -> None: ...
    async def back(self) -> None: ...


def browser_path() -> Optional[str]:
    """Edge (always on Windows), else Chrome."""
    if platform.system() == "Windows":
        roots = [os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("LOCALAPPDATA", "")]
        for root in roots:
            for relative in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                candidate = Path(root) / relative
                if root and candidate.exists():
                    return str(candidate)
        return None
    for candidate in ("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if Path(candidate).exists():
            return candidate
    return None


class EdgeWindow(BrowserDriver):
    """HARIKA's own browser window, driven over the DevTools protocol (local only)."""

    name = "HARIKA's browser window"

    def __init__(self, profile: Optional[Path] = None):
        self.profile = profile or data_path("browser", "profile")
        self.port: Optional[int] = None
        self.socket = None
        self.target_id = ""
        self._ids = count(1)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------- the window

    async def start(self) -> None:
        if self.socket is not None and await self._alive():
            return
        await self._close_socket()
        port = await self._running_port()
        if port is None:
            port = await self._launch()
        self.port = port
        await self._attach()

    async def _running_port(self) -> Optional[int]:
        marker = self.profile / "DevToolsActivePort"
        try:
            port = int(marker.read_text().splitlines()[0])
        except (OSError, ValueError, IndexError):
            return None
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                (await client.get(f"http://127.0.0.1:{port}/json/version")).raise_for_status()
            return port
        except httpx.HTTPError:
            return None

    async def _launch(self) -> int:
        exe = browser_path()
        if not exe:
            raise BrowserUnavailable("I couldn't find Microsoft Edge or Google Chrome on this computer")
        self.profile.mkdir(parents=True, exist_ok=True)
        (self.profile / "DevToolsActivePort").unlink(missing_ok=True)
        # Port 0: the browser picks a free port and writes it to DevToolsActivePort. It listens on
        # 127.0.0.1 only, and refuses connections from web pages.
        subprocess.Popen([exe, f"--user-data-dir={self.profile}", "--remote-debugging-port=0", "--no-first-run",
                          "--no-default-browser-check", "--new-window", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            port = await self._running_port()
            if port:
                return port
        raise BrowserUnavailable("The browser window didn't start")

    async def _attach(self) -> None:
        import websockets

        pages = await self._pages()
        page = pages[0] if pages else await self._new_page()
        self.target_id = page["id"]
        self.socket = await websockets.connect(page["webSocketDebuggerUrl"], max_size=16 * 1024 * 1024)
        await self._send("Page.enable")
        await self._send("Page.bringToFront")

    async def _pages(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            targets = (await client.get(f"http://127.0.0.1:{self.port}/json/list")).json()
        return [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]

    async def _new_page(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            return (await client.put(f"http://127.0.0.1:{self.port}/json/new?about:blank")).json()

    async def _alive(self) -> bool:
        try:
            await asyncio.wait_for(self._send("Runtime.evaluate", {"expression": "1", "returnByValue": True}), 3)
            return True
        except Exception:
            return False

    async def _close_socket(self) -> None:
        if self.socket is not None:
            try:
                await self.socket.close()
            except Exception:
                pass
        self.socket = None

    async def _follow_new_tab(self, before: List[str]) -> None:
        """A click that opened a new tab: carry on in that tab."""
        try:
            fresh = [p for p in await self._pages() if p["id"] not in before]
        except httpx.HTTPError:
            return
        if fresh:
            await self._close_socket()
            import websockets
            self.target_id = fresh[0]["id"]
            self.socket = await websockets.connect(fresh[0]["webSocketDebuggerUrl"], max_size=16 * 1024 * 1024)
            await self._send("Page.enable")
            await self._send("Page.bringToFront")

    # ------------------------------------------------------------- DevTools

    async def _send(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.socket is None:
            raise BrowserUnavailable("The browser window isn't open")
        async with self._lock:
            message_id = next(self._ids)
            await self.socket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
            while True:
                reply = json.loads(await asyncio.wait_for(self.socket.recv(), 30))
                if reply.get("id") == message_id:
                    if "error" in reply:
                        raise PageError(reply["error"].get("message", "the browser refused"))
                    return reply.get("result", {})

    async def _run(self, call: str) -> Any:
        """Runs a __harika call in the page (installing page.js first, since navigation clears it)."""
        result = await self._send("Runtime.evaluate", {
            "expression": f"{PAGE_SCRIPT}\n;{call}", "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            detail = result["exceptionDetails"]
            text = detail.get("exception", {}).get("description") or detail.get("text") or "the page refused"
            raise PageError(text.split("\n")[0].removeprefix("Error: "))
        return result.get("result", {}).get("value")

    async def _settle(self, seconds: float = 8.0) -> None:
        """Waits for the page to finish loading, then a moment for scripts to draw it."""
        deadline = time.monotonic() + seconds
        await asyncio.sleep(0.4)
        while time.monotonic() < deadline:
            try:
                if await self._run("__harika.ready()") == "complete":
                    break
            except Exception:
                pass  # mid-navigation
            await asyncio.sleep(0.4)
        await asyncio.sleep(0.8)

    # ------------------------------------------------------------- actions

    async def open(self, url: str) -> None:
        await self._send("Page.navigate", {"url": url})
        await self._settle()

    async def snapshot(self) -> Dict[str, Any]:
        return await self._run("__harika.snapshot()")

    async def click(self, element_id: int) -> None:
        before = [p["id"] for p in await self._pages()]
        point = await self._run(f"__harika.center({int(element_id)})")
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            await self._send("Input.dispatchMouseEvent", {"type": kind, "x": point["x"], "y": point["y"],
                                                          "button": "left", "clickCount": 1})
        await self._settle()
        await self._follow_new_tab(before)

    async def type(self, element_id: int, text: str) -> None:
        await self._run(f"__harika.focus({int(element_id)}, true)")
        await self._send("Input.insertText", {"text": text})  # real typing: replaces the selected text
        await asyncio.sleep(0.5)

    async def press_enter(self, element_id: int) -> None:
        await self._run(f"__harika.focus({int(element_id)}, false)")
        for kind in ("keyDown", "keyUp"):
            await self._send("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter",
                                                        "windowsVirtualKeyCode": 13, "text": "\r" if kind == "keyDown" else ""})
        await self._settle()

    async def choose(self, element_id: int, option: str) -> str:
        chosen = await self._run(f"__harika.choose({int(element_id)}, {json.dumps(option)})")
        await self._settle(4)
        return chosen

    async def scroll(self, direction: str) -> None:
        await self._run(f"__harika.scroll({json.dumps(direction)})")
        await asyncio.sleep(0.6)

    async def back(self) -> None:
        await self._run("history.back()")
        await self._settle()


edge_window = EdgeWindow()
