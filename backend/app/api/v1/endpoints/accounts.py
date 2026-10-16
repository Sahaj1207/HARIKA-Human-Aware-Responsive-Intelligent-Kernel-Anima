"""Settings > Accounts: connect Google for Calendar and Gmail.

Everything here is reachable only from this computer. Google returns the sign-in
to the callback below, on 127.0.0.1, in the user's own browser.
"""
import webbrowser

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.api.v1.endpoints.llm_settings import _callback_page, local_only
from app.core.live_events import live_events
from app.integrations.google.account import NotConnected, google_account

router = APIRouter(dependencies=[Depends(local_only)])


class GoogleClient(BaseModel):
    client_id: str
    client_secret: str


@router.get("")
async def accounts() -> dict:
    return {"google": google_account.status()}


@router.put("/google/client")
async def set_google_client(client: GoogleClient) -> dict:
    try:
        google_account.set_client(client.client_id, client.client_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"google": google_account.status()}


@router.post("/google/sign-in")
async def start_google_sign_in(request: Request, open_browser: bool = True) -> dict:
    try:
        url = google_account.start_sign_in(str(request.url_for("finish_google_sign_in")))
    except NotConnected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if open_browser:
        webbrowser.open(url)  # the desktop app's webview can't open external pages itself
    return {"auth_url": url}


@router.get("/google/callback", response_class=HTMLResponse, name="finish_google_sign_in")
async def finish_google_sign_in(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return _callback_page("Sign-in cancelled", "You can close this tab and try again from HARIKA's settings.", ok=False)
    try:
        email = await google_account.finish_sign_in(code, state)
    except Exception as exc:
        return _callback_page("Couldn't connect Google", str(exc), ok=False)
    live_events.publish("accounts_changed", service="google")
    return _callback_page("Google is connected", f"HARIKA can now use {email}'s calendar and email. You can close this tab.", ok=True)


@router.delete("/google")
async def disconnect_google() -> dict:
    await google_account.disconnect()
    live_events.publish("accounts_changed", service="google")
    return {"google": google_account.status()}


@router.post("/google/setup-page")
async def open_google_setup_page() -> dict:
    """Opens Google Cloud Console, where the user creates their OAuth client (a fixed address)."""
    webbrowser.open("https://console.cloud.google.com/auth/clients")
    return {"opened": True}
