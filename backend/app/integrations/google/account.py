"""Signing in to Google (OAuth 2.0 for installed apps, with PKCE) and calling its APIs.

The user's own Google Cloud "Desktop app" OAuth client is used. Google sends the
sign-in back to HARIKA on this computer (127.0.0.1). The refresh token and client
secret live in the OS credential store; only the client ID and the account's
email address are kept in HARIKA's settings file.
"""
import asyncio
import base64
import hashlib
import json
import logging
import secrets as pysecrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.cognition.llm import secrets
from app.core.paths import data_path

logger = logging.getLogger("harika.google")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPES = {
    "calendar": "https://www.googleapis.com/auth/calendar.events",
    "gmail_read": "https://www.googleapis.com/auth/gmail.readonly",
    "gmail_send": "https://www.googleapis.com/auth/gmail.send",
}
_IDENTITY = ["openid", "email"]
_SECRET = "google:client_secret"
_REFRESH = "google:refresh_token"
_SIGN_IN_TTL = 600


class NotConnected(RuntimeError):
    """Google isn't set up or signed in, or the needed permission wasn't granted."""


class GoogleError(RuntimeError):
    """Google answered with an error the user should hear about."""


class GoogleAccount:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("settings", "google.json")
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

    def status(self) -> Dict[str, Any]:
        data = self._load()
        granted = set(data.get("scopes", []))
        connected = bool(data.get("email")) and bool(secrets.get_secret(_REFRESH))
        return {
            "configured": bool(data.get("client_id")) and bool(secrets.get_secret(_SECRET)),
            "connected": connected,
            "email": data.get("email", "") if connected else "",
            "calendar": connected and SCOPES["calendar"] in granted,
            "email_read": connected and SCOPES["gmail_read"] in granted,
            "email_send": connected and SCOPES["gmail_send"] in granted,
        }

    def set_client(self, client_id: str, client_secret: str) -> None:
        client_id, client_secret = client_id.strip(), client_secret.strip()
        if not client_id.endswith(".apps.googleusercontent.com"):
            raise ValueError("That doesn't look like a Google OAuth client ID (it ends in .apps.googleusercontent.com).")
        if len(client_secret) < 10:
            raise ValueError("Paste the client secret from the same OAuth client.")
        secrets.set_secret(_SECRET, client_secret)
        self._save(client_id=client_id)

    # ------------------------------------------------------------- sign-in

    def start_sign_in(self, redirect_uri: str) -> str:
        client_id = self._load().get("client_id")
        if not client_id or not secrets.get_secret(_SECRET):
            raise NotConnected("Add your Google OAuth client first.")
        verifier = base64.urlsafe_b64encode(pysecrets.token_bytes(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = pysecrets.token_urlsafe(24)
        self._pending = {k: v for k, v in self._pending.items() if time.time() - v["created"] < _SIGN_IN_TTL}
        self._pending[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "created": time.time()}
        query = httpx.QueryParams({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(_IDENTITY + list(SCOPES.values())),
            "access_type": "offline",
            "prompt": "consent",  # always return a refresh token
            "include_granted_scopes": "true",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        })
        return f"{AUTH_URL}?{query}"

    async def finish_sign_in(self, code: str, state: str) -> str:
        pending = self._pending.pop(state, None)
        if pending is None or time.time() - pending["created"] > _SIGN_IN_TTL:
            raise ValueError("This sign-in link has expired or was already used. Start again from Settings.")
        data = self._load()
        async with httpx.AsyncClient(timeout=20.0) as client:
            reply = await client.post(TOKEN_URL, data={
                "code": code,
                "client_id": data.get("client_id", ""),
                "client_secret": secrets.get_secret(_SECRET) or "",
                "redirect_uri": pending["redirect_uri"],
                "grant_type": "authorization_code",
                "code_verifier": pending["verifier"],
            })
            tokens = reply.json()
            if reply.status_code != 200 or not tokens.get("refresh_token"):
                raise ValueError(tokens.get("error_description") or "Google didn't complete the sign-in.")
            profile = (await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})).json()
        secrets.set_secret(_REFRESH, tokens["refresh_token"])
        self._access_token, self._expires = tokens["access_token"], time.time() + int(tokens.get("expires_in", 3600)) - 60
        self._save(email=profile.get("email", ""), scopes=tokens.get("scope", "").split())
        return profile.get("email", "")

    async def disconnect(self) -> None:
        token = secrets.get_secret(_REFRESH)
        if token:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(REVOKE_URL, data={"token": token})
            except Exception as exc:
                logger.warning(f"[Google] Revoking access failed (removed locally anyway): {exc}")
        secrets.delete_secret(_REFRESH)
        self._access_token, self._expires = None, 0.0
        self._save(email="", scopes=[])

    # ------------------------------------------------------------- API calls

    def require(self, feature: str) -> None:
        """Raise NotConnected with a helpful message unless `feature` ('calendar', 'email_read', 'email_send') is usable."""
        status = self.status()
        if not status["connected"]:
            raise NotConnected("Google isn't connected yet. Sign in under Settings > Accounts")
        if not status[feature]:
            what = "your calendar" if feature == "calendar" else "reading your email" if feature == "email_read" else "sending email"
            raise NotConnected(f"Google didn't give me permission for {what}. Sign in again under Settings > Accounts and allow it")

    async def _token(self) -> str:
        async with self._refresh_lock:
            if self._access_token and time.time() < self._expires:
                return self._access_token
            refresh = secrets.get_secret(_REFRESH)
            if not refresh:
                raise NotConnected("Google isn't connected yet. Sign in under Settings > Accounts")
            async with httpx.AsyncClient(timeout=15.0) as client:
                reply = await client.post(TOKEN_URL, data={
                    "client_id": self._load().get("client_id", ""),
                    "client_secret": secrets.get_secret(_SECRET) or "",
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                })
            if reply.status_code != 200:
                if reply.json().get("error") == "invalid_grant":
                    raise NotConnected("Google signed HARIKA out. Sign in again under Settings > Accounts")
                raise GoogleError("Google isn't responding right now")
            tokens = reply.json()
            self._access_token, self._expires = tokens["access_token"], time.time() + int(tokens.get("expires_in", 3600)) - 60
            return self._access_token

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Authenticated call; returns parsed JSON (or None for an empty reply)."""
        token = await self._token()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                reply = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        except httpx.HTTPError as exc:
            raise GoogleError("I couldn't reach Google. Check your internet connection") from exc
        if reply.status_code == 401:
            self._access_token = None
            raise NotConnected("Google signed HARIKA out. Sign in again under Settings > Accounts")
        if reply.status_code >= 400:
            try:
                message = reply.json().get("error", {}).get("message", "")
            except ValueError:
                message = ""
            logger.warning(f"[Google] {method} {url.split('?')[0]} -> {reply.status_code} {message}")
            raise GoogleError(f"Google refused that ({message or reply.status_code})")
        return reply.json() if reply.content else None

    async def gather(self, method: str, urls: List[str], **kwargs: Any) -> List[Any]:
        return list(await asyncio.gather(*(self.request(method, url, **kwargs) for url in urls)))


google_account = GoogleAccount()
