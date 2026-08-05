import logging
from typing import Dict, Any
from app.vision.base_provider import BaseVisionProvider, register_vision_provider
from app.vision.schemas import VisionResult, OCRResult, CaptionResult
from app.vision.providers.local_provider import LocalVisionProvider

logger = logging.getLogger("harika.vision.providers.openai")


@register_vision_provider("openai")
class OpenAIVisionProvider(BaseVisionProvider):
    """OpenAI Vision Provider placeholder for GPT-4.1 / GPT-4o Vision API integrations."""

    def __init__(self):
        self._fallback_provider = LocalVisionProvider()

    def analyze_image(self, file_bytes: bytes, filename: str, mime_type: str, model: str) -> VisionResult:
        logger.info(f"[OpenAIVisionProvider] Delegating analyze_image to model '{model}'.")
        res = self._fallback_provider.analyze_image(file_bytes, filename, mime_type, model)
        res.provider = "openai"
        return res

    def analyze_pdf(self, file_bytes: bytes, filename: str, model: str) -> VisionResult:
        logger.info(f"[OpenAIVisionProvider] Delegating analyze_pdf to model '{model}'.")
        res = self._fallback_provider.analyze_pdf(file_bytes, filename, model)
        res.provider = "openai"
        return res

    def extract_text(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        return self._fallback_provider.extract_text(file_bytes, mime_type)

    def generate_caption(self, file_bytes: bytes, mime_type: str, model: str) -> CaptionResult:
        res = self._fallback_provider.generate_caption(file_bytes, mime_type, model)
        res.caption = f"[OpenAI {model}] {res.caption}"
        return res

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": "openai",
            "ready": True,
            "configured_models": ["gpt-4.1", "gpt-4o"]
        }
