"""Which model HARIKA uses for each job, and the plumbing to switch at runtime.

HARIKA has two model roles:
- understanding: turns requests into structured actions (short JSON; speed matters)
- conversation: answers questions and chats (quality matters)
Each role points at a service + model. Changes apply to the next request.
"""
import asyncio
import base64
import hashlib
import json
import logging
import re
import secrets as pysecrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.cognition.base_provider import BaseLLMProvider
from app.cognition.llm import secrets
from app.cognition.llm.catalog import ROLES, SERVICES, LLMService, get_service
from app.cognition.llm.providers import AnthropicProvider, GeminiProvider, OpenAICompatibleProvider
from app.core.paths import data_path

logger = logging.getLogger("harika.llm")

_SETTINGS_FILE = data_path("settings", "llm.json")


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

    def _raw(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def backups_enabled(self) -> bool:
        """Whether other connected services (and the local model) stand in when the chosen one fails."""
        return self._raw().get("use_backups", True) is not False

    def set_backups(self, enabled: bool) -> None:
        data = {**self._raw(), **self.load(), "use_backups": bool(enabled)}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def set_role(self, role: str, service_id: str, model: str) -> None:
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'.")
        if get_service(service_id) is None:
            raise ValueError(f"Unknown service '{service_id}'.")
        data = {**self._raw(), **self.load()}
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


# Cloud services tried as backups, fastest first. Gemini comes last: its free tier is small
# (about 20 requests a day per model), so it's kept for looking at the screen.
_BACKUP_ORDER = ("groq", "openrouter", "openai", "anthropic", "gemini")
_COOLDOWN_SECONDS = 60  # a service that just failed is skipped for a minute (longer if it says so)
_failed_at: Dict[str, float] = {}
_rest_until: Dict[str, float] = {}
_SHORT_WAIT_SECONDS = 20  # a service asking to wait this long or less is waited for, not skipped


_failures_in_a_row: Dict[str, int] = {}


def resting(service_id: str) -> bool:
    """Skipped for now: it asked us to wait (rate limit), or failed twice in a row within a minute.
    One blip doesn't count; the backups are often much slower."""
    if time.time() < _rest_until.get(service_id, 0):
        return True
    recent = time.time() - _failed_at.get(service_id, 0) < _COOLDOWN_SECONDS
    return recent and _failures_in_a_row.get(service_id, 0) >= 2


def note_failure(service_id: str, retry_after: Optional[float] = None) -> None:
    _failed_at[service_id] = time.time()
    _failures_in_a_row[service_id] = _failures_in_a_row.get(service_id, 0) + 1
    if retry_after:
        _rest_until[service_id] = time.time() + retry_after


def note_success(service_id: str) -> None:
    for record in (_failed_at, _rest_until, _failures_in_a_row):
        record.pop(service_id, None)


class RoleProvider(BaseLLMProvider):
    """Provider for a role that follows the user's current choice on every call.

    If the chosen service fails (offline, rate-limited, key rejected), the request
    quietly goes to the next connected service and finally to the model on this
    computer, so HARIKA keeps working. Turned off in Settings > Brain.
    """

    def __init__(self, role: str, store: LLMSettings = llm_settings):
        self.role = role
        self.store = store

    def current(self) -> BaseLLMProvider:
        choice = self.store.load()[self.role]
        return build_provider(choice["service"], choice["model"])

    @staticmethod
    async def _ask(provider, messages, system_prompt, json_mode):
        try:
            return await provider.generate_response(messages, system_prompt, json_mode=json_mode)
        except TypeError:
            return await provider.generate_response(messages, system_prompt)

    def chain(self) -> List[Dict[str, str]]:
        """[{service, model}] in the order they are tried."""
        choice = self.store.load()[self.role]
        chain = [choice]
        if not self.store.backups_enabled():
            return chain
        for service_id in _BACKUP_ORDER:
            service = get_service(service_id)
            model = service.suggested.get(self.role, "") if service else ""
            if service_id != choice["service"] and model and is_connected(service):
                chain.append({"service": service_id, "model": model})
        if choice["service"] != "ollama":
            from app.core.config import settings
            chain.append({"service": "ollama", "model": settings.OLLAMA_MODEL})
        return chain

    def is_local(self) -> bool:
        """Whether this role runs on the computer (slow to read long prompts on a CPU)."""
        service = get_service(self.store.load()[self.role]["service"])
        return service is None or service.kind == "ollama"

    async def generate_response(self, messages, system_prompt, json_mode: bool = False) -> Dict[str, Any]:
        chain = self.chain()
        usable = [c for c in chain if not resting(c["service"])] or chain[-1:]
        result: Dict[str, Any] = {}
        for index, choice in enumerate(usable):
            if index:  # a backup uses a model its service still offers
                choice = {**choice, "model": await usable_model(choice["service"], self.role) or choice["model"]}
            provider = build_provider(choice["service"], choice["model"])
            result = await self._ask(provider, messages, system_prompt, json_mode)
            wait = result.get("retry_after") if result.get("error") else None
            if wait and wait <= _SHORT_WAIT_SECONDS:
                # "Try again in a few seconds" (a per-minute limit): waiting beats a much slower backup.
                await asyncio.sleep(wait + 0.5)
                result = await self._ask(provider, messages, system_prompt, json_mode)
            elif not result.get("error") and not str(result.get("response", "")).strip():
                result = await self._ask(provider, messages, system_prompt, json_mode)  # an empty reply: ask once more
            if not result.get("error") and not str(result.get("response", "")).strip():
                result = {**result, "error": True, "response": f"{choice['service']} returned an empty reply."}
            if not result.get("error"):
                if index:
                    result["fallback_from"] = usable[0]["service"]
                    logger.info(f"[LLM] {self.role}: used {choice['service']} because {usable[0]['service']} failed.")
                note_success(choice["service"])
                return result
            note_failure(choice["service"], result.get("retry_after"))
            logger.warning(f"[LLM] {self.role}: {choice['service']} failed: {result.get('response', '')[:160]}")
        return result


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


async def verify_key(service_id: str, api_key: str) -> List[str]:
    """Prove a key works before saving it, then return the models it can use.

    OpenRouter's model list is public (it answers 200 even for a bad key), so its
    key is checked against the authenticated /key endpoint first.
    """
    service = get_service(service_id)
    if service is not None and service.id == "openrouter":
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            reply = await client.get(f"{service.base_url}/key", headers={"Authorization": f"Bearer {api_key}"})
            reply.raise_for_status()
    return await list_models(service_id, api_key=api_key)


# Models a service lists that can't hold a conversation (speech, safety filters, images, embeddings).
_NOT_CHAT = ("whisper", "tts", "orpheus", "guard", "safeguard", "embed", "image", "transcribe", "computer-use", "allam")


def pick_default(service: LLMService, role: str, available: List[str]) -> str:
    """The suggested model if this account has it, else the best available alternative."""
    suggested = service.suggested.get(role, "")
    if suggested and (not available or suggested in available):
        return suggested
    if service.kind == "ollama":
        from app.core.config import settings
        if settings.OLLAMA_MODEL in available:
            return settings.OLLAMA_MODEL
    chat = [m for m in available if not any(word in m.lower() for word in _NOT_CHAT)]
    def newest_first(name: str):
        return [int(n) for n in re.findall(r"\d+", name)]

    for hint in service.fallbacks.get(role, []):
        matches = sorted((m for m in chat if hint in m.lower() and "preview" not in m.lower()), key=newest_first, reverse=True)
        if matches:
            return matches[0]
    if role == "vision":
        return ""  # never guess that a model can see
    return chat[0] if chat else (available[0] if available else suggested)


_MODEL_LISTS: Dict[str, Tuple[float, List[str]]] = {}


async def usable_model(service_id: str, role: str) -> str:
    """A model of this service that exists today (lists are cached for six hours)."""
    service = get_service(service_id)
    if service is None:
        return ""
    cached = _MODEL_LISTS.get(service_id)
    if cached is None or time.time() - cached[0] > 6 * 3600:
        try:
            _MODEL_LISTS[service_id] = (time.time(), await list_models(service_id))
        except Exception:
            _MODEL_LISTS[service_id] = (time.time(), [])  # unknown: trust the suggestion
    return pick_default(service, role, _MODEL_LISTS[service_id][1])


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


async def describe_with_availability() -> Dict[str, Any]:
    """describe(), plus whether on-device servers are actually running right now."""
    import asyncio

    info = describe()

    async def reachable(service_id: str) -> bool:
        try:
            await asyncio.wait_for(list_models(service_id), timeout=1.5)
            return True
        except Exception:
            return False

    local = [s for s in info["services"] if s["on_device"]]
    results = await asyncio.gather(*(reachable(s["id"]) for s in local))
    for service, running in zip(local, results):
        service["connected"] = running
        service["available"] = running
    return info


def describe() -> Dict[str, Any]:
    """Everything the Settings screen needs; never includes keys."""
    choices = llm_settings.load()
    return {
        "use_backups": llm_settings.backups_enabled(),
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
