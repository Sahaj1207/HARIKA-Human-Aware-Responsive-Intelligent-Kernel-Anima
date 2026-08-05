import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from app.vision.schemas import VisionResult, OCRResult, CaptionResult

logger = logging.getLogger("harika.vision.provider")

# Registry mapping provider keys (e.g. "local", "ollama", "openai", "gemini") to provider classes
_VISION_PROVIDER_REGISTRY: Dict[str, Type["BaseVisionProvider"]] = {}


def register_vision_provider(name: str):
    """Decorator to register a Vision Provider class in the global factory registry."""
    def decorator(cls: Type["BaseVisionProvider"]):
        _VISION_PROVIDER_REGISTRY[name.lower()] = cls
        logger.info(f"[VisionRegistry] Registered vision provider '{name.lower()}' -> {cls.__name__}")
        return cls
    return decorator


def get_vision_provider_class(name: str) -> Type["BaseVisionProvider"]:
    """Resolves provider class dynamically by name from the registry."""
    key = name.lower().strip()
    if key not in _VISION_PROVIDER_REGISTRY:
        logger.warning(f"[VisionRegistry] Provider '{name}' not found in registry. Fallback to 'local'. Available: {list(_VISION_PROVIDER_REGISTRY.keys())}")
        if "local" in _VISION_PROVIDER_REGISTRY:
            return _VISION_PROVIDER_REGISTRY["local"]
        raise ValueError(f"No vision provider registered for '{name}' and no 'local' fallback available.")
    return _VISION_PROVIDER_REGISTRY[key]


class BaseVisionProvider(ABC):
    """Abstract Base Class for all Vision Engine Providers in HARIKA."""

    @abstractmethod
    def analyze_image(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        model: str
    ) -> VisionResult:
        """Analyzes an image and returns structured VisionResult."""
        pass

    @abstractmethod
    def analyze_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        model: str
    ) -> VisionResult:
        """Parses and analyzes a PDF document page-by-page."""
        pass

    @abstractmethod
    def extract_text(
        self,
        file_bytes: bytes,
        mime_type: str
    ) -> OCRResult:
        """Extracts OCR text, blocks, numbers, and code snippets from binary visual assets."""
        pass

    @abstractmethod
    def generate_caption(
        self,
        file_bytes: bytes,
        mime_type: str,
        model: str
    ) -> CaptionResult:
        """Generates concise summary and tags for visual assets."""
        pass

    @abstractmethod
    def health_check() -> Dict[str, Any]:
        """Returns health status of provider and underlying models."""
        pass
