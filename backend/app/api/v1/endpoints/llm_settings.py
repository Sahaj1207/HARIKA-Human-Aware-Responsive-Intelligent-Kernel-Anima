"""Settings > Brain: choose which language model HARIKA uses for each job.

Only reachable from this computer, and API keys are never returned.
"""
import html
import webbrowser

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.cognition.llm import secrets
from app.cognition.llm.catalog import ROLES, get_service
from app.cognition.llm.manager import (
    check_role, describe, describe_with_availability, list_models, llm_settings, offered_models, openrouter_sign_in,
    pick_default, verify_key,
)
from app.core.live_events import live_events

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def local_only(request: Request) -> None:
    if request.client is None or request.client.host not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Model settings can only be changed on this computer.")


router = APIRouter(dependencies=[Depends(local_only)])


class RoleChoice(BaseModel):
    service: str
    model: str


class ApiKey(BaseModel):
    api_key: str


def _service_or_404(service_id: str):
    service = get_service(service_id)
    if service is None:
        raise HTTPException(status_code=404, detail=f"Unknown service '{service_id}'.")
    return service


@router.get("")
async def get_llm_settings():
    return await describe_with_availability()


@router.put("/roles/{role}")
async def choose_model(role: str, choice: RoleChoice):
    if role not in ROLES:
        raise HTTPException(status_code=404, detail=f"Unknown role '{role}'.")
    service = _service_or_404(choice.service)
    if service.needs_key and not secrets.has_key(service.id):
        raise HTTPException(status_code=409, detail=f"Connect {service.name} before choosing one of its models.")
    if not service.on_device:
        offered = await offered_models(service.id)
        if offered and choice.model not in offered:
            raise HTTPException(status_code=400, detail=f"{service.name} doesn't offer {choice.model}. Pick one of its models.")
    llm_settings.set_role(role, service.id, choice.model)
    live_events.publish("llm_settings_changed", role=role)
    return describe()


class BackupsChoice(BaseModel):
    enabled: bool


@router.put("/backups")
async def choose_backups(choice: BackupsChoice):
    llm_settings.set_backups(choice.enabled)
    live_events.publish("llm_settings_changed", role="backups")
    return describe()


@router.get("/services/{service_id}/models")
async def get_models(service_id: str):
    service = _service_or_404(service_id)
    try:
        models = await list_models(service.id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't list {service.name} models: {exc}") from exc
    return {
        "models": models,
        "suggested": {role: pick_default(service, role, models) for role in ROLES},
    }


@router.put("/services/{service_id}/key")
async def connect_with_key(service_id: str, body: ApiKey):
    service = _service_or_404(service_id)
    if not service.needs_key:
        raise HTTPException(status_code=400, detail=f"{service.name} doesn't use an API key.")
    key = body.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Paste an API key.")
    try:
        models = await verify_key(service.id, key)  # proves the key works before saving it
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = "That key was rejected." if status in (401, 403) else f"{service.name} answered with HTTP {status}."
        raise HTTPException(status_code=400, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't reach {service.name}: {exc}") from exc
    try:
        secrets.set_key(service.id, key)
    except secrets.SecretStoreUnavailable as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    live_events.publish("llm_settings_changed", service=service.id)
    return {"connected": True, "models": models, "suggested": {r: pick_default(service, r, models) for r in ROLES}}


@router.delete("/services/{service_id}/key")
async def disconnect(service_id: str):
    service = _service_or_404(service_id)
    secrets.delete_key(service.id)
    # Roles that used this service go back to the default: another connected service, else on-device.
    for role, choice in llm_settings.load().items():
        if choice["service"] == service.id:
            llm_settings.clear_role(role)
    live_events.publish("llm_settings_changed", service=service.id)
    return describe()


@router.post("/services/{service_id}/open-setup-page")
async def open_setup_page(service_id: str):
    """Open the download page for an on-device service (catalog URL only)."""
    service = _service_or_404(service_id)
    if not service.setup_url:
        raise HTTPException(status_code=400, detail=f"{service.name} has no installer page.")
    webbrowser.open(service.setup_url)
    return {"opened": service.setup_url}


@router.get("/local/status")
async def local_model_status():
    """Is Ollama running, and does it have the model recommended for this computer?"""
    from app.cognition.llm.local_models import model_download, ollama_status
    return {**await ollama_status(), "downloading": model_download.running}


class DownloadRequest(BaseModel):
    model: str


@router.post("/local/download", status_code=202)
async def download_local_model(body: DownloadRequest):
    """Start downloading a recommended model; progress arrives as 'model_download' live events."""
    from app.cognition.llm.local_models import SMALL_MODEL, model_download, ollama_status
    from app.core.config import settings

    if body.model not in {settings.OLLAMA_MODEL, SMALL_MODEL}:
        raise HTTPException(status_code=400, detail="HARIKA only downloads its recommended models here.")
    if not (await ollama_status())["running"]:
        raise HTTPException(status_code=409, detail="Ollama isn't running. Install it, open it, then try again.")
    if not model_download.start(body.model):
        raise HTTPException(status_code=409, detail="A model is already downloading.")
    return {"started": body.model}


@router.post("/roles/{role}/test")
async def test_role(role: str):
    if role not in ROLES:
        raise HTTPException(status_code=404, detail=f"Unknown role '{role}'.")
    return await check_role(role)


@router.get("/openrouter/start")
async def start_openrouter_sign_in(request: Request, open_browser: bool = False):
    callback = str(request.url_for("finish_openrouter_sign_in")).replace("127.0.0.1", "localhost")
    url = openrouter_sign_in.start(callback)
    if open_browser:
        # The desktop app's webview can't open external pages itself.
        webbrowser.open(url)
    return {"auth_url": url}


@router.post("/services/{service_id}/open-key-page")
async def open_key_page(service_id: str):
    """Open the service's own "create API key" page (from the catalog, never a caller-supplied URL)."""
    service = _service_or_404(service_id)
    if not service.key_url:
        raise HTTPException(status_code=400, detail=f"{service.name} doesn't use an API key.")
    webbrowser.open(service.key_url)
    return {"opened": service.key_url}


@router.get("/openrouter/callback", response_class=HTMLResponse, name="finish_openrouter_sign_in")
async def finish_openrouter_sign_in(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return _callback_page("Sign-in cancelled", "You can close this tab and try again from HARIKA's settings.", ok=False)
    try:
        await openrouter_sign_in.finish(code, state)
    except Exception as exc:
        return _callback_page("Couldn't connect OpenRouter", str(exc), ok=False)
    live_events.publish("llm_settings_changed", service="openrouter")
    return _callback_page("OpenRouter is connected", "You can close this tab and go back to HARIKA.", ok=True)


def _callback_page(title: str, message: str, ok: bool) -> str:
    color = "#34C759" if ok else "#FF3B30"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>
:root {{ color-scheme: light dark; }}
body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:Canvas; color:CanvasText;
  font: 17px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif; }}
main {{ text-align:center; max-width:30rem; padding:2rem; }}
.mark {{ width:56px; height:56px; border-radius:50%; margin:0 auto 1.25rem; background:{color}; }}
h1 {{ font-size:22px; font-weight:600; margin:0 0 .5rem; letter-spacing:-.01em; }}
p {{ margin:0; opacity:.65; }}
</style></head><body><main><div class="mark"></div><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></main></body></html>"""
