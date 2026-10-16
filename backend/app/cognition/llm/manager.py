"""Which model HARIKA uses for each job, and the plumbing to switch at runtime.

HARIKA has two model roles:
- understanding: turns requests into structured actions (short JSON; speed matters)
- conversation: answers questions and chats (quality matters)
Each role points at a service + model. Changes apply to the next request.
"""
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

from app.cognition.base_provider import BaseLLMProvider
from app.cognition.llm import secrets
from app.cognition.llm.catalog import ROLES, SERVICES, LLMService, get_service
from app.cognition.llm.providers import AnthropicProvider, GeminiProvider, OpenAICompatibleProvider

logger = logging.getLogger("harika.llm")

_SETTINGS_FILE = Path(__file__).resolve().parents[3] / "data" / "settings" / "llm.json"


class LLMSettings:
    """Role -> {service, model}, persisted as plain JSON (no secrets in it)."""

    def __init__(self, path: Path = _SETTINGS_FILE):
        self.path = path
        self._lock = threading.Lock()

    def _defaults(self) -> Dict[str, Dict[str, str]]:
        from app.core.config import settings
        return {role: {"service": "ollama", "model": settings.OLLAMA_MODEL} for role in ROLES}

    def load(self) -> Dict[str, Dict[str, str]]:
        with self._lock:
            data = self._defaults()
            if self.path.exists():
                try:
                    stored = json.loads(self.path.read_text(encoding="utf-8"))
                    for role in ROLES:
                        if isinstance(stored.get(role), dict) and get_service(stored[role].get("service", "")):
                            data[role] = {"service": stored[role]["service"], "model": str(stored[role].get("model", ""))}
                except (OSError, json.JSONDecodeError):
                    logger.warning("[LLM] Settings unreadable; using defaults.")
            return data

    def set_role(self, role: str, service_id: str, model: str) -> None:
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'.")
        if get_service(service_id) is None:
            raise ValueError(f"Unknown service '{service_id}'.")
        data = self.load()
        data[role] = {"service": service_id, "model": model}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


llm_settings = LLMSettings()


def is_connected(service: LLMService) -> bool:
    return not service.needs_key or secrets.has_key(service.id)


def build_provider(service_id: str, model: str) -> BaseLLMProvider:
    service = get_service(service_id)
    if service is None:
        raise ValueError(f"Unknown service '{service_id}'.")
    key = secrets.get_key(service.id) if service.needs_key else None
    if service.kind == "ollama":
        from app.cognition.providers.ollama_provider import OllamaProvider
        return OllamaProvider(model=model)
    if service.kind == "anthropic":
        return AnthropicProvider(model, key, service.base_url)
    if service.kind == "gemini":
        return GeminiProvider(model, key, service.base_url)
    return OpenAICompatibleProvider(model, key, service.base_url, service.name)


class RoleProvider(BaseLLMProvider):
    """Provider for a role that follows the user's current choice on every call."""

    def __init__(self, role: str, store: LLMSettings = llm_settings):
        self.role = role
        self.store = store

    def current(self) -> BaseLLMProvider:
        choice = self.store.load()[self.role]
        return build_provider(choice["service"], choice["model"])

    async def generate_response(self, messages, system_prompt, json_mode: bool = False) -> Dict[str, Any]:
        provider = self.current()
        try:
            return await provider.generate_response(messages, system_prompt, json_mode=json_mode)
        except TypeError:
            return await provider.generate_response(messages, system_prompt)


async def list_models(service_id: str, api_key: Optional[str] = None) -> List[str]:
    """Models the service offers this account. Raises httpx errors on failure."""
    service = get_service(service_id)
    if service is None:
        raise ValueError(f"Unknown service '{service_id}'.")
    key = api_key or (secrets.get_key(service_id) if service.needs_key else None)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
        if service.kind == "ollama":
            from app.core.config import settings
            reply = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            reply.raise_for_status()
            return sorted(m["name"] for m in reply.json().get("models", []))
        if service.kind == "anthropic":
            reply = await client.get(f"{service.base_url}/models", headers={"x-api-key": key or "", "anthropic-version": "2023-06-01"})
            reply.raise_for_status()
            return [m["id"] for m in reply.json().get("data", [])]
        if service.kind == "gemini":
            reply = await client.get(f"{service.base_url}/models", headers={"x-goog-api-key": key or ""}, params={"pageSize": 200})
            reply.raise_for_status()
            return [
                m["name"].removeprefix("models/") for m in reply.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        reply = await client.get(f"{service.base_url}/models", headers=headers)
        reply.raise_for_status()
        return sorted(m["id"] for m in reply.json().get("data", []))


def pick_default(service: LLMService, role: str, available: List[str]) -> str:
    """The suggested model if this account has it, else a sensible available one."""
    suggested = service.suggested.get(role, "")
    if suggested and (not available or suggested in available):
        return suggested
    if service.kind == "ollama":
        from app.core.config import settings
        if settings.OLLAMA_MODEL in available:
            return settings.OLLAMA_MODEL
    return available[0] if available else suggested


async def check_role(role: str) -> Dict[str, Any]:
    """Send a tiny prompt through a role's model; used by the 'Test' button."""
    provider = RoleProvider(role)
    started = time.perf_counter()
    result = await provider.generate_response(
        [{"role": "user", "content": "Reply with the single word: ready"}],
        "You are a connectivity check. Follow the instruction exactly.",
    )
    return {
        "ok": not result.get("error") and bool(result.get("response")),
        "reply": result.get("response", ""),
        "model": result.get("model"),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


class OpenRouterSignIn:
    """OAuth PKCE: openrouter.ai/auth -> our callback with ?code -> exchange for a user key."""

    AUTH_URL = "https://openrouter.ai/auth"
    EXCHANGE_URL = "https://openrouter.ai/api/v1/auth/keys"

    def __init__(self):
        self._pending: Dict[str, Dict[str, Any]] = {}

    def start(self, callback_url: str) -> str:
        verifier = base64.urlsafe_b64encode(pysecrets.token_bytes(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = pysecrets.token_urlsafe(24)
        self._pending = {k: v for k, v in self._pending.items() if time.time() - v["created"] < 600}
        self._pending[state] = {"verifier": verifier, "created": time.time()}
        query = httpx.QueryParams({
            "callback_url": callback_url,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "key_label": "HARIKA",
        })
        return f"{self.AUTH_URL}?{query}"

    async def finish(self, code: str, state: str) -> None:
        pending = self._pending.pop(state, None)
        if pending is None or time.time() - pending["created"] > 600:
            raise ValueError("This sign-in link has expired or was already used. Start again from Settings.")
        async with httpx.AsyncClient(timeout=20.0) as client:
            reply = await client.post(self.EXCHANGE_URL, json={
                "code": code, "code_verifier": pending["verifier"], "code_challenge_method": "S256",
            })
            reply.raise_for_status()
        key = reply.json().get("key")
        if not key:
            raise ValueError("OpenRouter didn't return a key.")
        secrets.set_key("openrouter", key)


openrouter_sign_in = OpenRouterSignIn()


def describe() -> Dict[str, Any]:
    """Everything the Settings screen needs; never includes keys."""
    choices = llm_settings.load()
    return {
        "roles": {
            role: {**choice, "on_device": bool(get_service(choice["service"]) and get_service(choice["service"]).on_device)}
            for role, choice in choices.items()
        },
        "services": [
            {
                "id": s.id, "name": s.name, "on_device": s.on_device, "needs_key": s.needs_key,
                "sign_in": s.sign_in, "key_url": s.key_url, "blurb": s.blurb, "connected": is_connected(s),
            }
            for s in SERVICES
        ],
    }
