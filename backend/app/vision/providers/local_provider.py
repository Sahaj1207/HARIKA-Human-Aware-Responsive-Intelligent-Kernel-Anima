import uuid
import time
import logging
from typing import Dict, Any
from app.vision.base_provider import BaseVisionProvider, register_vision_provider
from app.vision.schemas import (
    VisionResult, OCRResult, OCRBlock, ImageAnalysisResult, PDFAnalysisResult, PDFPageAnalysis, CaptionResult
)

logger = logging.getLogger("harika.vision.providers.local")


@register_vision_provider("local")
class LocalVisionProvider(BaseVisionProvider):
    """Local Vision Provider delivering heuristic & embedded OCR/analysis for zero-dependency local execution."""

    def analyze_image(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        model: str
    ) -> VisionResult:
        from app.vision.image_analyzer import image_analyzer
        from app.vision.caption import caption_engine

        start_time = time.time()
        res_id = f"vis-{uuid.uuid4().hex[:8]}"

        ocr_res = self.extract_text(file_bytes, mime_type)
        img_analysis = image_analyzer.analyze(file_bytes, filename, mime_type, ocr_res)
        caption_res = caption_engine.generate_caption(filename, mime_type, img_analysis, ocr_res)

        latency = round((time.time() - start_time) * 1000, 2)
        summary = f"Processed {filename} ({img_analysis.classification}) via {model}. Extracted {ocr_res.word_count} words."

        return VisionResult(
            id=res_id,
            filename=filename,
            file_type=mime_type,
            provider="local",
            model=model,
            ocr=ocr_res,
            image_analysis=img_analysis,
            caption=caption_res,
            summary=summary,
            latency_ms=latency
        )


    def analyze_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        model: str
    ) -> VisionResult:
        from app.vision.pdf import pdf_engine
        from app.vision.caption import caption_engine

        start_time = time.time()
        res_id = f"vis-pdf-{uuid.uuid4().hex[:8]}"

        pdf_analysis = pdf_engine.parse_pdf(file_bytes, filename)
        extracted_text = pdf_analysis.extracted_text

        ocr_blocks = [OCRBlock(text=extracted_text, category="text", confidence=0.95)]
        ocr_res = OCRResult(
            raw_text=extracted_text,
            blocks=ocr_blocks,
            word_count=len(extracted_text.split()),
            latency_ms=round((time.time() - start_time) * 1000, 2)
        )

        caption_res = CaptionResult(
            caption=f"PDF Document: {filename}",
            detailed_summary=f"PDF document '{filename}' containing {pdf_analysis.total_pages} page(s) and {len(extracted_text.split())} words.",
            tags=["pdf", "document"]
        )

        latency = round((time.time() - start_time) * 1000, 2)
        return VisionResult(
            id=res_id,
            filename=filename,
            file_type="application/pdf",
            provider="local",
            model=model,
            ocr=ocr_res,
            pdf_analysis=pdf_analysis,
            caption=caption_res,
            summary=f"Parsed PDF {filename} ({pdf_analysis.total_pages} page(s)).",
            latency_ms=latency
        )


    def extract_text(
        self,
        file_bytes: bytes,
        mime_type: str
    ) -> OCRResult:
        from app.vision.ocr import ocr_engine
        return ocr_engine.process_asset(file_bytes, mime_type)


    def generate_caption(
        self,
        file_bytes: bytes,
        mime_type: str,
        model: str
    ) -> CaptionResult:
        return CaptionResult(
            caption=f"Visual asset analyzed via {model}.",
            detailed_summary=f"Visual document asset ({mime_type}) processed locally.",
            tags=["image", mime_type.split('/')[-1], "processed"]
        )

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": "local",
            "engine": "HARIKA Heuristic Local Engine",
            "ready": True
        }
