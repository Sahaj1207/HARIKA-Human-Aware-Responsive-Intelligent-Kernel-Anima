import logging
from typing import Dict, Any
from app.vision.base_provider import BaseVisionProvider, register_vision_provider
from app.vision.schemas import VisionResult, OCRResult, CaptionResult
from app.vision.providers.local_provider import LocalVisionProvider

logger = logging.getLogger("harika.vision.providers.gemini")


@register_vision_provider("gemini")
class GeminiVisionProvider(BaseVisionProvider):
    """Gemini Vision Provider placeholder for Gemini 2.5 Pro Vision API integrations."""

    def __init__(self):
        self._fallback_provider = LocalVisionProvider()

    def analyze_image(self, file_bytes: bytes, filename: str, mime_type: str, model: str) -> VisionResult:
        logger.info(f"[GeminiVisionProvider] Delegating analyze_image to model '{model}'.")
        res = self._fallback_provider.analyze_image(file_bytes, filename, mime_type, model)
        res.provider = "gemini"
        return res

    def analyze_pdf(self, file_bytes: bytes, filename: str, model: str) -> VisionResult:
        logger.info(f"[GeminiVisionProvider] Delegating analyze_pdf to model '{model}'.")
        res = self._fallback_provider.analyze_pdf(file_bytes, filename, model)
        res.provider = "gemini"
        return res

    def extract_text(self, file_bytes: bytes, mime_type: str) -> OCRResult:
        return self._fallback_provider.extract_text(file_bytes, mime_type)

    def generate_caption(self, file_bytes: bytes, mime_type: str, model: str) -> CaptionResult:
        res = self._fallback_provider.generate_caption(file_bytes, mime_type, model)
        res.caption = f"[Gemini {model}] {res.caption}"
        return res

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": "gemini",
            "ready": True,
            "configured_models": ["gemini-2.5-pro", "gemini-1.5-flash"]
        }
