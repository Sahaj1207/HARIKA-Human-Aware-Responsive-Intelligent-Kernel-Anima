"""The language-model services HARIKA can use, described as data."""
from typing import Dict, List, Optional

from pydantic import BaseModel


class LLMService(BaseModel):
    id: str
    name: str
    kind: str  # "ollama" | "openai_compatible" | "anthropic" | "gemini"
    base_url: str = ""
    on_device: bool = False
    needs_key: bool = True
    sign_in: bool = False  # supports "Sign in" (OAuth) instead of pasting a key
    key_url: str = ""  # where users create a key
    setup_url: str = ""  # where users install it (on-device services)
    blurb: str = ""
    # Suggested models when the service can't list its own (or before connecting).
    suggested: Dict[str, str] = {}


SERVICES: List[LLMService] = [
    LLMService(
        id="ollama", name="On this computer (Ollama)", kind="ollama", on_device=True, needs_key=False,
        setup_url="https://ollama.com/download",
        blurb="Private and free. Runs on your own hardware, so speed depends on your computer.",
        suggested={"understanding": "", "conversation": ""},
    ),
    LLMService(
        id="lmstudio", name="On this computer (LM Studio)", kind="openai_compatible",
        base_url="http://localhost:1234/v1", on_device=True, needs_key=False,
        setup_url="https://lmstudio.ai",
        blurb="Private and free. Uses the model loaded in LM Studio's local server.",
    ),
    LLMService(
        id="openrouter", name="OpenRouter", kind="openai_compatible", base_url="https://openrouter.ai/api/v1",
        sign_in=True, key_url="https://openrouter.ai/settings/keys",
        blurb="Sign in once to use models from OpenAI, Anthropic, Google, Meta and more.",
        suggested={"understanding": "openai/gpt-4o-mini", "conversation": "anthropic/claude-sonnet-4.5",
                   "vision": "google/gemini-2.5-flash"},
    ),
    LLMService(
        id="openai", name="OpenAI", kind="openai_compatible", base_url="https://api.openai.com/v1",
        key_url="https://platform.openai.com/api-keys",
        blurb="GPT models. Needs an API key (billed separately from ChatGPT Plus).",
        suggested={"understanding": "gpt-4o-mini", "conversation": "gpt-4o", "vision": "gpt-4o-mini"},
    ),
    LLMService(
        id="anthropic", name="Anthropic", kind="anthropic", base_url="https://api.anthropic.com/v1",
        key_url="https://console.anthropic.com/settings/keys",
        blurb="Claude models. Needs an API key (billed separately from Claude Pro).",
        suggested={"understanding": "claude-haiku-5-5", "conversation": "claude-sonnet-5-5", "vision": "claude-haiku-5-5"},
    ),
    LLMService(
        id="gemini", name="Google Gemini", kind="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        key_url="https://aistudio.google.com/app/apikey",
        blurb="Gemini models. Google AI Studio offers a free tier.",
        suggested={"understanding": "gemini-2.5-flash", "conversation": "gemini-2.5-flash", "vision": "gemini-2.5-flash"},
    ),
    LLMService(
        id="groq", name="Groq", kind="openai_compatible", base_url="https://api.groq.com/openai/v1",
        key_url="https://console.groq.com/keys",
        blurb="Very fast open models. Has a free tier.",
        suggested={"understanding": "llama-3.1-8b-instant", "conversation": "llama-3.3-70b-versatile",
                   "vision": "meta-llama/llama-4-scout-17b-16e-instruct"},
    ),
]

ROLES = ("understanding", "conversation")


def get_service(service_id: str) -> Optional[LLMService]:
    return next((s for s in SERVICES if s.id == service_id), None)
