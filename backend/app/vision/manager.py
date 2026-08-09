import logging
from typing import Optional, Dict, Any, List
from app.core.config import settings
import app.vision.providers  # Trigger provider registrations
from app.vision.schemas import VisionResult, OCRResult, VisionMetrics
from app.vision.base_provider import BaseVisionProvider, get_vision_provider_class
from app.vision.preprocessing import vision_preprocessor, VisionPreprocessor
from app.vision.history import vision_history_manager, VisionHistoryManager
from app.vision.metrics import vision_metrics_manager, VisionMetricsManager

logger = logging.getLogger("harika.vision.manager")



class VisionManager:
    """Central Vision Engine Orchestrator dynamically resolving provider & model from configuration."""

    def __init__(
        self,
        preprocessor: Optional[VisionPreprocessor] = None,
        history: Optional[VisionHistoryManager] = None,
        metrics: Optional[VisionMetricsManager] = None
    ):
        self.preprocessor = preprocessor or vision_preprocessor
        self.history = history or vision_history_manager
        self.metrics = metrics or vision_metrics_manager

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "subsystem": "VisionManager",
            "name": "Visual Analysis Engine",
            "features": ["Image Description", "Optical Character Recognition (OCR)", "Document Reading"]
        }

    def _get_provider(self, override_provider: Optional[str] = None) -> BaseVisionProvider:

        provider_name = override_provider or settings.VISION_PROVIDER
        provider_cls = get_vision_provider_class(provider_name)
        return provider_cls()

    def process_image(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None
    ) -> VisionResult:
        from app.planning.events import planning_event_bus, PlanningEventType
        planning_event_bus.emit(PlanningEventType.VISION_STARTED, {"filename": filename, "content_type": content_type})
        try:
            clean_name, mime = self.preprocessor.validate_file(file_bytes, filename, content_type)
            provider = self._get_provider(provider_override)
            model = model_override or settings.VISION_MODEL

            logger.info(f"[VisionManager] Processing image '{clean_name}' using provider '{provider.__class__.__name__}' and model '{model}'.")
            result = provider.analyze_image(file_bytes, clean_name, mime, model)
            self.history.record_result(result)
            planning_event_bus.emit(PlanningEventType.VISION_COMPLETED, result.model_dump())
            return result
        except Exception as e:
            planning_event_bus.emit(PlanningEventType.VISION_FAILED, {"filename": filename, "error": str(e)})
            raise

    def process_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None
    ) -> VisionResult:
        from app.planning.events import planning_event_bus, PlanningEventType
        planning_event_bus.emit(PlanningEventType.VISION_STARTED, {"filename": filename, "content_type": content_type})
        try:
            clean_name, mime = self.preprocessor.validate_file(file_bytes, filename, content_type)
            provider = self._get_provider(provider_override)
            model = model_override or settings.VISION_MODEL

            logger.info(f"[VisionManager] Processing PDF '{clean_name}' using provider '{provider.__class__.__name__}' and model '{model}'.")
            result = provider.analyze_pdf(file_bytes, clean_name, model)
            self.history.record_result(result)
            planning_event_bus.emit(PlanningEventType.VISION_COMPLETED, result.model_dump())
            return result
        except Exception as e:
            planning_event_bus.emit(PlanningEventType.VISION_FAILED, {"filename": filename, "error": str(e)})
            raise


    def extract_ocr(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        provider_override: Optional[str] = None
    ) -> OCRResult:
        clean_name, mime = self.preprocessor.validate_file(file_bytes, filename, content_type)
        provider = self._get_provider(provider_override)

        logger.info(f"[VisionManager] Extracting OCR for '{clean_name}' using provider '{provider.__class__.__name__}'.")
        return provider.extract_text(file_bytes, mime)

    def store_visual_memory(self, result: VisionResult, user_id: str = "default") -> Optional[Any]:
        """Integrates with Memory Engine to store structured facts extracted from visual assets into Cognitive Memory."""
        try:
            import uuid
            from app.memory.manager import memory_manager
            from app.memory.models import MemoryItem, MemoryCategory

            mem_id = f"mem-vis-{uuid.uuid4().hex[:8]}"
            content = f"Visual Asset ({result.file_type}): {result.summary}. OCR: {result.ocr.raw_text[:200] if result.ocr else 'N/A'}"
            tags = result.caption.tags if result.caption else ["visual", "vision"]

            item = MemoryItem(
                id=mem_id,
                category=MemoryCategory.NOTES,
                title=f"Visual Fact: {result.filename}",
                content=content,
                importance=0.8,
                confidence=0.9,
                source="vision_engine",
                tags=tags
            )

            stored = memory_manager.add_memory(item, user_id=user_id)
            logger.info(f"[VisionManager] Stored visual memory '{stored.title}' ({stored.id}).")
            return stored
        except Exception as e:
            logger.error(f"[VisionManager] Failed to store visual memory: {e}")
            return None

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.history.get_history(limit=limit)


    def get_metrics(self) -> VisionMetrics:
        return self.metrics.get_metrics()

    def health_check(self, provider_override: Optional[str] = None) -> Dict[str, Any]:
        provider = self._get_provider(provider_override)
        return provider.health_check()


vision_manager = VisionManager()
