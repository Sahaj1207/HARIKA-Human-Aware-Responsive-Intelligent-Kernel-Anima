import time
import httpx
from typing import List, Dict, Any
from app.cognition.base_provider import BaseLLMProvider
from app.core.config import settings
from app.core.logging import logger


class OllamaProvider(BaseLLMProvider):
    """Real Ollama LLM provider implementation for local model inference."""

    def __init__(self, model: str = ""):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.provider_name = "ollama"

    @staticmethod
    def _keep_alive(value: str):
        """Ollama takes durations as strings ("30m") but bare seconds/-1 only as numbers."""
        text = str(value).strip()
        return int(text) if text.lstrip("-").isdigit() else text

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        json_mode: bool = False
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # Format chat history with system prompt
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            role = "user" if msg.get("sender") == "user" or msg.get("role") == "user" else "assistant"
            formatted_messages.append({"role": role, "content": msg.get("content", "")})

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
            "keep_alive": self._keep_alive(settings.OLLAMA_KEEP_ALIVE),
            # Same context size on every request: a different num_ctx makes Ollama reload the model.
            "options": {"num_ctx": settings.OLLAMA_NUM_CTX},
        }
        if json_mode:
            # Structured interpretation: constrain output to JSON and decode deterministically.
            payload["format"] = "json"
            payload["options"].update({"temperature": 0, "num_predict": 256})

        url = f"{self.base_url}/api/chat"

        try:
            # 120 seconds HTTP timeout for local LLM model inference
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                content = data.get("message", {}).get("content", "").strip()
                if not content:
                    content = "HARIKA core received an empty response payload from local inference."

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                # Log model name, total inference time, and timeout status (False)
                logger.info(
                    f"[Ollama Inference] Model: {self.model} | Latency: {latency_ms}ms | Timeout: False"
                )

                return {
                    "response": content,
                    "provider": self.provider_name,
                    "model": self.model,
                    "latency_ms": latency_ms
                }

        except httpx.ConnectError:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(
                f"[Ollama Inference] Model: {self.model} | Latency: {latency_ms}ms | Timeout: False - Connection Failed at {url}"
            )
            return {
                "response": "HARIKA Offline Mode: Unable to connect to local Ollama instance at " + self.base_url,
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency_ms
            }

        except httpx.TimeoutException:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(
                f"[Ollama Inference] Model: {self.model} | Latency: {latency_ms}ms | Timeout: True - Exceeded 120s limit"
            )
            return {
                "response": "HARIKA Cognition Timeout: Local model inference exceeded the 120-second limit.",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency_ms
            }

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                f"[Ollama Inference Error] Model: {self.model} | Latency: {latency_ms}ms | Error: {str(e)}"
            )
            return {
                "response": f"HARIKA Cognition Notice: {str(e)}",
                "provider": self.provider_name,
                "model": self.model,
                "latency_ms": latency_ms
            }
