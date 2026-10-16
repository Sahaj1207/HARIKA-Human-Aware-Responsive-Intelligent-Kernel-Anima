"""Cloud and local chat providers behind HARIKA's BaseLLMProvider contract.

Every provider returns {"response", "provider", "model", "latency_ms"} and, on
failure, a plain-language explanation as the response plus "error": True, so
chat shows something actionable and the interpreter falls back safely.
"""
import time
from typing import Any, Dict, List, Optional

import httpx

from app.cognition.base_provider import BaseLLMProvider

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _roles(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """HARIKA history uses role or sender; providers want user/assistant."""
    out = []
    for msg in messages:
        role = "user" if msg.get("sender") == "user" or msg.get("role") == "user" else "assistant"
        content = str(msg.get("content", ""))
        if content:
            out.append({"role": role, "content": content})
    return out


def _explain(service: str, exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        reason = {
            401: "the API key was rejected",
            403: "this key isn't allowed to use that model",
            404: "that model doesn't exist for this account",
            429: "the rate limit or credit balance was reached",
        }.get(status, f"it answered with HTTP {status}")
        return f"I couldn't get an answer from {service}: {reason}. You can check this in Settings, under Brain."
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return f"I couldn't reach {service}. Check your internet connection, or that the local server is running."
    if isinstance(exc, httpx.TimeoutException):
        return f"{service} took too long to answer."
    return f"Something went wrong talking to {service}: {exc}"


class _HTTPProvider(BaseLLMProvider):
    service_name = "provider"

    def __init__(self, model: str, api_key: Optional[str] = None, base_url: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider_name = self.service_name

    async def generate_response(self, messages, system_prompt, json_mode: bool = False) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            text = await self._complete(_roles(messages), system_prompt, json_mode)
            error = False
        except Exception as exc:
            text, error = _explain(self.service_name, exc), True
        return {
            "response": (text or "").strip(),
            "provider": self.provider_name,
            "model": self.model,
            "latency_ms": int((time.perf_counter() - start) * 1000),
            **({"error": True} if error else {}),
        }

    async def _complete(self, messages, system_prompt, json_mode) -> str:  # pragma: no cover - abstract
        raise NotImplementedError


class OpenAICompatibleProvider(_HTTPProvider):
    """OpenAI, OpenRouter, Groq, LM Studio and any other /chat/completions API."""

    def __init__(self, model: str, api_key: Optional[str], base_url: str, service_name: str):
        self.service_name = service_name
        super().__init__(model, api_key, base_url)

    async def _complete(self, messages, system_prompt, json_mode) -> str:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
            body["temperature"] = 0
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        if "openrouter.ai" in self.base_url:
            headers["X-Title"] = "HARIKA"  # app name shown in the user's OpenRouter activity
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reply = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            reply.raise_for_status()
        return reply.json()["choices"][0]["message"]["content"]


class AnthropicProvider(_HTTPProvider):
    service_name = "Anthropic"

    async def _complete(self, messages, system_prompt, json_mode) -> str:
        body: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            # The Messages API needs the conversation to start with a user turn.
            "messages": messages if messages and messages[0]["role"] == "user" else [{"role": "user", "content": "Hello"}, *messages],
        }
        if json_mode:
            body["temperature"] = 0
        headers = {"x-api-key": self.api_key or "", "anthropic-version": "2023-06-01"}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reply = await client.post(f"{self.base_url}/messages", json=body, headers=headers)
            reply.raise_for_status()
        return "".join(block.get("text", "") for block in reply.json().get("content", []) if block.get("type") == "text")


class GeminiProvider(_HTTPProvider):
    service_name = "Google Gemini"

    async def _complete(self, messages, system_prompt, json_mode) -> str:
        body: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                for m in messages
            ],
        }
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json", "temperature": 0}
        model = self.model if self.model.startswith("models/") else f"models/{self.model}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            reply = await client.post(
                f"{self.base_url}/{model}:generateContent", json=body, headers={"x-goog-api-key": self.api_key or ""}
            )
            reply.raise_for_status()
        candidates = reply.json().get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        return "".join(part.get("text", "") for part in parts)
