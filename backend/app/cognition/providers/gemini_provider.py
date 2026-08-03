import time
from typing import List, Dict, Any
from app.cognition.base_provider import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Placeholder Gemini provider implementing the BaseLLMProvider interface."""

    def __init__(self):
        self.provider_name = "gemini"
        self.model = "gemini-1.5-pro"

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "response": "Gemini Provider placeholder: API integration pending configuration.",
            "provider": self.provider_name,
            "model": self.model,
            "latency_ms": latency_ms
        }
