"""Spotify: signing in (OAuth 2.0 with PKCE, no client secret) and calling its Web API.

The user registers a free app on developer.spotify.com and pastes its Client ID in
Settings > Accounts (a build can also include one: secrets/spotify-client.json).
Spotify sends the sign-in back to HARIKA on this computer (127.0.0.1). The refresh
token lives in the OS credential store; only the client ID and the account's display
name are kept in HARIKA's settings file. Starting and controlling playback needs a
Premium account (Spotify's rule); the rest works on any account.
"""
import asyncio
import base64
import hashlib
import json
import logging
import re
import secrets as pysecrets
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.cognition.llm import secrets
from app.core.paths import data_path

logger = logging.getLogger("harika.spotify")

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
SCOPES = ["user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing",
          "user-library-read", "user-library-modify", "playlist-read-private", "playlist-modify-private",
          "playlist-modify-public"]
_REFRESH = "spotify:refresh_token"
_SIGN_IN_TTL = 600
_CLIENT_ID = re.compile(r"^[0-9a-f]{32}$")


class SpotifyNotConnected(RuntimeError):
    """Spotify isn't usable yet; the message says what to do."""


class SpotifyError(RuntimeError):
    """Spotify refused or failed; the message is shown to the user."""


def bundled_client_id() -> str:
    """A client ID shipped with this build (secrets/spotify-client.json), if any."""
    files = [Path(__file__).resolve().parents[3] / "secrets" / "spotify-client.json"]  # development
    if getattr(sys, "frozen", False):  # the installer puts it next to the bundled backend
        files.insert(0, Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "spotify-client.json")
    for path in files:
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("client_id", "")
            if _CLIENT_ID.match(value):
                return value
        except (OSError, ValueError):
            continue
    return ""


class SpotifyAccount:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("settings", "spotify.json")
        self._lock = threading.Lock()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._access_token: Optional[str] = None
        self._expires = 0.0
        self._refresh_lock = asyncio.Lock()

    # ------------------------------------------------------------- settings

    def _load(self) -> Dict[str, Any]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            except (OSError, json.JSONDecodeError):
                return {}

    def _save(self, **changes: Any) -> None:
        data = {**self._load(), **changes}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def client_id(self) -> str:
        return self._load().get("client_id") or bundled_client_id()

    def status(self) -> Dict[str, Any]:
        data = self._load()
        connected = bool(self.client_id()) and bool(secrets.get_secret(_REFRESH))
        return {"configured": bool(self.client_id()), "own_client": bool(data.get("client_id")),
                "connected": connected, "name": data.get("name", "") if connected else "",
                "premium": connected and data.get("product") == "premium"}

    def set_client(self, client_id: str) -> None:
        client_id = client_id.strip()
        if not _CLIENT_ID.match(client_id):
            raise ValueError("That doesn't look like a Spotify Client ID (32 letters and numbers, from your app's page "
                             "on developer.spotify.com).")
        self._forget_sign_in()  # a sign-in belongs to the client it was made with
        self._save(client_id=client_id)

    def _forget_sign_in(self) -> None:
        secrets.delete_secret(_REFRESH)
        self._access_token, self._expires = None, 0.0
        self._save(name="", product="")

    # ------------------------------------------------------------- sign-in

    def start_sign_in(self, redirect_uri: str) -> str:
        client_id = self.client_id()
        if not client_id:
            raise SpotifyNotConnected("Add your Spotify app's Client ID in Settings > Accounts first.")
        verifier = base64.urlsafe_b64encode(pysecrets.token_bytes(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = pysecrets.token_urlsafe(24)
        self._pending = {k: v for k, v in self._pending.items() if time.time() - v["created"] < _SIGN_IN_TTL}
        self._pending[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "created": time.time()}
        query = httpx.QueryParams({
            "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES), "code_challenge_method": "S256", "code_challenge": challenge, "state": state,
        })
        return f"{AUTH_URL}?{query}"

    async def finish_sign_in(self, code: str, state: str) -> str:
        pending = self._pending.pop(state, None)
        if pending is None or time.time() - pending["created"] > _SIGN_IN_TTL:
            raise ValueError("This sign-in link has expired or was already used. Start again from Settings.")
        async with httpx.AsyncClient(timeout=20.0) as client:
            reply = await client.post(TOKEN_URL, data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": pending["redirect_uri"],
                "client_id": self.client_id(), "code_verifier": pending["verifier"],
            })
            tokens = reply.json()
            if reply.status_code != 200 or not tokens.get("refresh_token"):
                raise ValueError(tokens.get("error_description") or "Spotify didn't complete the sign-in.")
            profile = (await client.get(f"{API}/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})).json()
        secrets.set_secret(_REFRESH, tokens["refresh_token"])
        self._access_token, self._expires = tokens["access_token"], time.time() + int(tokens.get("expires_in", 3600)) - 60
        name = profile.get("display_name") or profile.get("id") or "your account"
        self._save(name=name, product=profile.get("product", ""))
        return name

    def disconnect(self) -> None:
        # Spotify has no token-revoke endpoint; access is removed from the account page by the user.
        self._forget_sign_in()

    # ------------------------------------------------------------- API calls

    async def _token(self) -> str:
        async with self._refresh_lock:
            if self._access_token and time.time() < self._expires:
                return self._access_token
            refresh = secrets.get_secret(_REFRESH)
            if not refresh or not self.client_id():
                raise SpotifyNotConnected("Spotify isn't connected yet. Connect it in Settings > Accounts")
            async with httpx.AsyncClient(timeout=15.0) as client:
                reply = await client.post(TOKEN_URL, data={"grant_type": "refresh_token", "refresh_token": refresh,
                                                           "client_id": self.client_id()})
            if reply.status_code != 200:
                if reply.json().get("error") == "invalid_grant":
                    self._forget_sign_in()
                    raise SpotifyNotConnected("Spotify signed HARIKA out. Connect it again in Settings > Accounts")
                raise SpotifyError("Spotify isn't responding right now")
            tokens = reply.json()
            if tokens.get("refresh_token"):  # Spotify may rotate it
                secrets.set_secret(_REFRESH, tokens["refresh_token"])
            self._access_token, self._expires = tokens["access_token"], time.time() + int(tokens.get("expires_in", 3600)) - 60
            return self._access_token

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        token = await self._token()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                reply = await client.request(method, f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs)
        except httpx.HTTPError as exc:
            raise SpotifyError("I couldn't reach Spotify. Check your internet connection") from exc
        if reply.status_code == 401:
            self._access_token = None
            raise SpotifyNotConnected("Spotify signed HARIKA out. Connect it again in Settings > Accounts")
        if reply.status_code >= 400:
            try:
                error = reply.json().get("error", {})
                reason, message = error.get("reason", ""), error.get("message", "")
            except ValueError:
                reason, message = "", ""
            logger.warning(f"[Spotify] {method} {path.split('?')[0]} -> {reply.status_code} {reason or message}")
            if reason == "PREMIUM_REQUIRED" or reply.status_code == 403:
                raise SpotifyError("Spotify only lets apps control playback on Premium accounts")
            if reason == "NO_ACTIVE_DEVICE" or (reply.status_code == 404 and path.startswith("/me/player")):
                raise SpotifyError("NO_ACTIVE_DEVICE")
            raise SpotifyError(f"Spotify refused that ({message or reply.status_code})")
        return reply.json() if reply.content and reply.status_code != 204 else None


spotify_account = SpotifyAccount()
