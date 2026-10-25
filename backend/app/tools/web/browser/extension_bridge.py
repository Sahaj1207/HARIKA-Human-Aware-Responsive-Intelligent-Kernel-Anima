"""HARIKA's browser extension: website tasks in the user's own Chrome or Edge, with their sign-ins.

The extension (browser-extension/ in the repository) connects to HARIKA on this computer
over a WebSocket and does what it's asked in ONE tab it opened itself (grouped and
labelled "HARIKA"), using the same page.js as HARIKA's own window. It never looks at the
user's other tabs.

Only the extension may connect: the connection must come from a browser extension
(chrome-extension:// origin, which web pages can't fake) and start with the pairing code
shown in HARIKA's Settings, which the user pastes into the extension once.
"""
import asyncio
import json
import logging
import secrets as random_secrets
from itertools import count
from typing import Any, Dict, Optional

from app.tools.web.browser.driver import BrowserDriver, BrowserUnavailable, PageError

logger = logging.getLogger("harika.tools.browser.extension")

_SECRET_NAME = "browser_extension_code"
_EXTENSION_ORIGINS = ("chrome-extension://", "moz-extension://", "extension://")
_REPLY_SECONDS = 30.0


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes (0/O, 1/I)
_unsaved_code = {"code": ""}  # used only when the system keychain isn't available


def _make_code() -> str:
    return "-".join("".join(random_secrets.choice(_ALPHABET) for _ in range(5)) for _ in range(4))


def pairing_code() -> str:
    """The code the extension must present (made once, kept in the system keychain)."""
    from app.cognition.llm import secrets
    try:
        return secrets.get_secret(_SECRET_NAME) or new_pairing_code()
    except secrets.SecretStoreUnavailable:
        _unsaved_code["code"] = _unsaved_code["code"] or _make_code()
        return _unsaved_code["code"]


def new_pairing_code() -> str:
    """A fresh code; the extension paired with the old one is signed out."""
    from app.cognition.llm import secrets
    code = _make_code()
    try:
        secrets.set_secret(_SECRET_NAME, code)
    except secrets.SecretStoreUnavailable:
        _unsaved_code["code"] = code
    extension_bridge.disconnect()
    return code


def origin_allowed(origin: Optional[str]) -> bool:
    return bool(origin) and origin.startswith(_EXTENSION_ORIGINS)


class ExtensionBridge(BrowserDriver):
    name = "your browser"

    def __init__(self):
        self.socket = None
        self.browser = ""
        self._ids = count(1)
        self._waiting: Dict[int, asyncio.Future] = {}

    def connected(self) -> bool:
        return self.socket is not None

    def disconnect(self) -> None:
        socket, self.socket = self.socket, None
        if socket is not None:
            try:
                asyncio.get_running_loop().create_task(socket.close(code=4401))
            except RuntimeError:
                pass

    # ------------------------------------------------------------- the connection

    async def serve(self, websocket) -> None:
        """One extension connection, from its hello to its goodbye."""
        from fastapi import WebSocketDisconnect

        if not origin_allowed(websocket.headers.get("origin")):
            await websocket.close(code=4403)
            return
        await websocket.accept()
        try:
            hello = json.loads(await asyncio.wait_for(websocket.receive_text(), 10))
        except (asyncio.TimeoutError, ValueError, WebSocketDisconnect):
            await websocket.close(code=4400)
            return
        if not isinstance(hello, dict) or not random_secrets.compare_digest(str(hello.get("code", "")), pairing_code()):
            await websocket.send_text(json.dumps({"type": "rejected", "reason": "That pairing code isn't right."}))
            await websocket.close(code=4401)
            return
        previous, self.socket = self.socket, websocket
        if previous is not None:
            try:
                await previous.close(code=4000)
            except Exception:
                pass
        self.browser = str(hello.get("browser") or "your browser")[:60]
        await websocket.send_text(json.dumps({"type": "welcome"}))
        self._announce()
        logger.info(f"[Extension] Connected from {self.browser}")
        try:
            while True:
                message = json.loads(await websocket.receive_text())
                waiting = self._waiting.pop(message.get("id"), None) if isinstance(message, dict) else None
                if waiting is not None and not waiting.done():
                    waiting.set_result(message)
        except (WebSocketDisconnect, ValueError, RuntimeError):
            pass
        finally:
            if self.socket is websocket:
                self.socket = None
                self._announce()
            for waiting in self._waiting.values():
                if not waiting.done():
                    waiting.set_exception(BrowserUnavailable("The browser extension disconnected"))
            self._waiting.clear()

    def _announce(self) -> None:
        from app.core.live_events import live_events
        live_events.publish("browser_extension", connected=self.connected(), browser=self.browser)

    async def _call(self, command: str, timeout: float = _REPLY_SECONDS, **args: Any) -> Any:
        if self.socket is None:
            raise BrowserUnavailable("HARIKA's browser extension isn't connected")
        message_id = next(self._ids)
        future = asyncio.get_running_loop().create_future()
        self._waiting[message_id] = future
        await self.socket.send_text(json.dumps({"id": message_id, "cmd": command, "args": args}))
        try:
            reply = await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            self._waiting.pop(message_id, None)
            raise PageError("the browser didn't answer in time") from exc
        if not reply.get("ok"):
            raise PageError(str(reply.get("error") or "the browser refused"))
        return reply.get("result")

    # ------------------------------------------------------------- actions (in HARIKA's tab)

    async def start(self) -> None:
        await self._call("start")

    async def open(self, url: str) -> None:
        await self._call("open", timeout=45, url=url)

    async def snapshot(self) -> Dict[str, Any]:
        return await self._call("page", name="snapshot", params=[])

    async def click(self, element_id: int) -> None:
        await self._call("page", name="click", params=[int(element_id)], settle=True)

    async def type(self, element_id: int, text: str) -> None:
        await self._call("page", name="type", params=[int(element_id), text])

    async def press_enter(self, element_id: int) -> None:
        await self._call("page", name="pressEnter", params=[int(element_id)], settle=True)

    async def choose(self, element_id: int, option: str) -> str:
        return await self._call("page", name="choose", params=[int(element_id), option], settle=True)

    async def scroll(self, direction: str) -> None:
        await self._call("page", name="scroll", params=[direction])

    async def back(self) -> None:
        await self._call("back")


extension_bridge = ExtensionBridge()
