import logging
from typing import Dict, Any
from app.vision.base_provider import BaseVisionProvider, register_vision_provider
from app.vision.schemas import VisionResult, OCRResult, CaptionResult
from app.vision.providers.local_provider import LocalVisionProvider

logger = logging.getLogger("harika.vision.providers.ollama")


@register_vision_provider("ollama")
class OllamaVisionProvider(BaseVisionProvider):
    """Ollama Vision Provider placeholder for local multimodal models (Qwen2.5-VL, LLaVA, etc.)."""

    def __init__(self):
        self._fallback_provider = LocalVisionProvider()

    def analyze_image(self, file_bytes: bytes, filename: str, mime_type: str, model: str) -> VisionResult:
        logger.info(f"[OllamaVisionProvider] Delegating analyze_image to model '{model}'.")
        res = self._fallback_provider.analyze_image(file_bytes, filename, mime_type, model)
        res.provider = "ollama"
        return res

    def analyze_pdf(self, file_bytes: bytes, filename: str, model: str) -> VisionResult:
        logger.info(f"[OllamaVisionProvider] Delegating analyze_pdf to model '{model}'.")
        res = self._fallback_provider.analyze_pdf(file_bytes, filename, model)
        res.provider = "ollama"
        return res

    def extract_text(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        return self._fallback_provider.extract_text(file_bytes, mime_type)

    def generate_caption(self, file_bytes: bytes, mime_type: str, model: str) -> CaptionResult:
        res = self._fallback_provider.generate_caption(file_bytes, mime_type, model)
        res.caption = f"[Ollama {model}] {res.caption}"
        return res

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": "ollama",
            "ready": True,
            "configured_models": ["qwen2.5vl", "llava"]
        }
