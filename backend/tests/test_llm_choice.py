"""Choosing language models: providers, key storage, sign-in, settings API.

All HTTP is served by httpx.MockTransport and keys go to an in-memory keyring,
so nothing touches the network or the real OS credential store.
"""
import asyncio
import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import keyring
from keyring.backend import KeyringBackend

from app.cognition.llm import manager as llm_manager
from app.cognition.llm import secrets
from app.cognition.llm.manager import LLMSettings, OpenRouterSignIn, RoleProvider
from app.cognition.llm.providers import AnthropicProvider, GeminiProvider, OpenAICompatibleProvider

_real_client = httpx.AsyncClient


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.store = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


def fake_http(handler):
    """Patch httpx.AsyncClient so every request goes to `handler`."""
    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _real_client(*args, **kwargs)
    return patch("httpx.AsyncClient", side_effect=factory)


class ProviderRequestTests(unittest.TestCase):
    def test_openai_compatible_sends_json_mode_and_bearer_key(self):
        seen = {}

        def handler(request):
            seen.update(url=str(request.url), auth=request.headers.get("authorization"), body=json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"actions": []}'}}]})

        with fake_http(handler):
            provider = OpenAICompatibleProvider("gpt-4o-mini", "sk-test", "https://api.openai.com/v1", "OpenAI")
            result = asyncio.run(provider.generate_response([{"role": "user", "content": "hi"}], "sys", json_mode=True))
        self.assertEqual(result["response"], '{"actions": []}')
        self.assertEqual(seen["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer sk-test")
        self.assertEqual(seen["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(seen["body"]["messages"][0], {"role": "system", "content": "sys"})

    def test_anthropic_uses_messages_api_shape(self):
        seen = {}

        def handler(request):
            seen.update(headers=request.headers, body=json.loads(request.content))
            return httpx.Response(200, json={"content": [{"type": "text", "text": "Hello!"}]})

        with fake_http(handler):
            provider = AnthropicProvider("claude-haiku-5-5", "sk-ant", "https://api.anthropic.com/v1")
            result = asyncio.run(provider.generate_response([{"sender": "user", "content": "hi"}], "be brief"))
        self.assertEqual(result["response"], "Hello!")
        self.assertEqual(seen["headers"]["x-api-key"], "sk-ant")
        self.assertEqual(seen["body"]["system"], "be brief")
        self.assertEqual(seen["body"]["messages"], [{"role": "user", "content": "hi"}])

    def test_gemini_uses_system_instruction_and_json_mime(self):
        seen = {}

        def handler(request):
            seen.update(url=str(request.url), key=request.headers.get("x-goog-api-key"), body=json.loads(request.content))
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

        with fake_http(handler):
            provider = GeminiProvider("gemini-2.5-flash", "g-key", "https://generativelanguage.googleapis.com/v1beta")
            asyncio.run(provider.generate_response([{"role": "user", "content": "hi"}], "sys", json_mode=True))
        self.assertTrue(seen["url"].endswith("/models/gemini-2.5-flash:generateContent"))
        self.assertEqual(seen["key"], "g-key")
        self.assertEqual(seen["body"]["generationConfig"]["responseMimeType"], "application/json")

    def test_rejected_key_becomes_actionable_message(self):
        with fake_http(lambda request: httpx.Response(401, json={"error": "bad key"})):
            provider = OpenAICompatibleProvider("m", "bad", "https://api.groq.com/openai/v1", "Groq")
            result = asyncio.run(provider.generate_response([{"role": "user", "content": "hi"}], "sys"))
        self.assertTrue(result["error"])
        self.assertIn("API key was rejected", result["response"])
        self.assertIn("Settings", result["response"])


class RoleAndKeyTests(unittest.TestCase):
    def setUp(self):
        self.previous_keyring = keyring.get_keyring()
        keyring.set_keyring(MemoryKeyring())
        self.dir = tempfile.TemporaryDirectory(prefix="harika-llm-")
        self.store = LLMSettings(Path(self.dir.name) / "llm.json")

    def tearDown(self):
        keyring.set_keyring(self.previous_keyring)
        self.dir.cleanup()

    def test_defaults_are_on_device(self):
        roles = self.store.load()
        self.assertEqual({r["service"] for r in roles.values()}, {"ollama"})

    def test_role_provider_follows_the_current_choice(self):
        secrets.set_key("groq", "gsk-test")
        role = RoleProvider("conversation", store=self.store)
        self.assertEqual(type(role.current()).__name__, "OllamaProvider")
        self.store.set_role("conversation", "groq", "llama-3.3-70b-versatile")
        current = role.current()
        self.assertEqual((type(current).__name__, current.model, current.api_key),
                         ("OpenAICompatibleProvider", "llama-3.3-70b-versatile", "gsk-test"))

    def test_unknown_service_or_role_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.set_role("conversation", "made-up", "x")
        with self.assertRaises(ValueError):
            self.store.set_role("dreaming", "ollama", "x")

    def test_settings_file_never_contains_keys(self):
        secrets.set_key("openai", "sk-secret-value")
        self.store.set_role("understanding", "openai", "gpt-4o-mini")
        self.assertNotIn("sk-secret-value", (Path(self.dir.name) / "llm.json").read_text())
        with patch.object(llm_manager, "llm_settings", self.store):
            self.assertNotIn("sk-secret-value", json.dumps(llm_manager.describe()))

    def test_openrouter_sign_in_uses_pkce_and_stores_key(self):
        flow = OpenRouterSignIn()
        url = flow.start("http://localhost:8000/api/v1/settings/llm/openrouter/callback")
        query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        verifier = flow._pending[query["state"]]["verifier"]
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual((query["code_challenge"], query["code_challenge_method"]), (expected, "S256"))

        sent = {}

        def handler(request):
            sent.update(json.loads(request.content))
            return httpx.Response(200, json={"key": "sk-or-user"})

        with fake_http(handler):
            asyncio.run(flow.finish("auth-code", query["state"]))
        self.assertEqual(sent, {"code": "auth-code", "code_verifier": verifier, "code_challenge_method": "S256"})
        self.assertEqual(secrets.get_key("openrouter"), "sk-or-user")

        with self.assertRaises(ValueError):  # a state can only be used once
            asyncio.run(flow.finish("auth-code", query["state"]))


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app

        self.previous_keyring = keyring.get_keyring()
        keyring.set_keyring(MemoryKeyring())
        self.dir = tempfile.TemporaryDirectory(prefix="harika-llm-api-")
        self.store_patch = patch.object(llm_manager, "llm_settings", LLMSettings(Path(self.dir.name) / "llm.json"))
        self.store_patch.start()
        import app.api.v1.endpoints.llm_settings as endpoint
        self.endpoint_patch = patch.object(endpoint, "llm_settings", llm_manager.llm_settings)
        self.endpoint_patch.start()
        self.local = TestClient(app, client=("127.0.0.1", 50000))
        self.remote = TestClient(app, client=("192.168.1.20", 50000))

    def tearDown(self):
        self.endpoint_patch.stop()
        self.store_patch.stop()
        keyring.set_keyring(self.previous_keyring)
        self.dir.cleanup()

    def test_other_computers_cannot_read_or_change_settings(self):
        self.assertEqual(self.remote.get("/api/v1/settings/llm").status_code, 403)
        self.assertEqual(self.remote.put("/api/v1/settings/llm/services/openai/key", json={"api_key": "x"}).status_code, 403)

    def test_key_is_verified_before_saving(self):
        with fake_http(lambda request: httpx.Response(401)):
            bad = self.local.put("/api/v1/settings/llm/services/groq/key", json={"api_key": "nope"})
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(secrets.has_key("groq"))

        models = {"data": [{"id": "llama-3.3-70b-versatile"}, {"id": "llama-3.1-8b-instant"}]}
        with fake_http(lambda request: httpx.Response(200, json=models)):
            good = self.local.put("/api/v1/settings/llm/services/groq/key", json={"api_key": "gsk-ok"})
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.json()["suggested"]["understanding"], "llama-3.1-8b-instant")
        self.assertTrue(secrets.has_key("groq"))

    def test_openrouter_bad_key_rejected_even_though_model_list_is_public(self):
        def handler(request):
            if request.url.path.endswith("/key"):
                return httpx.Response(401)
            return httpx.Response(200, json={"data": [{"id": "openai/gpt-4o-mini"}]})

        with fake_http(handler):
            reply = self.local.put("/api/v1/settings/llm/services/openrouter/key", json={"api_key": "sk-or-bad"})
        self.assertEqual(reply.status_code, 400)
        self.assertFalse(secrets.has_key("openrouter"))

    def test_only_recommended_models_can_be_downloaded(self):
        reply = self.local.post("/api/v1/settings/llm/local/download", json={"model": "some/huge-model:405b"})
        self.assertEqual(reply.status_code, 400)

    def test_download_needs_ollama_running(self):
        from app.core.config import settings
        with fake_http(lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused"))):
            reply = self.local.post("/api/v1/settings/llm/local/download", json={"model": settings.OLLAMA_MODEL})
        self.assertEqual(reply.status_code, 409)

    def test_smaller_model_recommended_for_low_memory_computers(self):
        from app.cognition.llm import local_models
        from app.core.config import settings
        with patch.object(local_models, "total_memory_gb", return_value=6.0):
            self.assertEqual(local_models.recommended_model()["model"], local_models.SMALL_MODEL)
        with patch.object(local_models, "total_memory_gb", return_value=16.0):
            self.assertEqual(local_models.recommended_model()["model"], settings.OLLAMA_MODEL)
        self.assertGreater(local_models.total_memory_gb() or 0, 1)  # real reading on this machine

    def test_choosing_a_model_requires_connecting_first(self):
        refused = self.local.put("/api/v1/settings/llm/roles/conversation", json={"service": "openai", "model": "gpt-4o"})
        self.assertEqual(refused.status_code, 409)
        secrets.set_key("openai", "sk-ok")
        chosen = self.local.put("/api/v1/settings/llm/roles/conversation", json={"service": "openai", "model": "gpt-4o"})
        self.assertEqual(chosen.json()["roles"]["conversation"], {"service": "openai", "model": "gpt-4o", "on_device": False})

    def test_disconnecting_returns_roles_to_on_device_model(self):
        secrets.set_key("openai", "sk-ok")
        self.local.put("/api/v1/settings/llm/roles/understanding", json={"service": "openai", "model": "gpt-4o-mini"})
        after = self.local.delete("/api/v1/settings/llm/services/openai/key").json()
        self.assertEqual(after["roles"]["understanding"]["service"], "ollama")
        self.assertFalse(secrets.has_key("openai"))


if __name__ == "__main__":
    unittest.main()
