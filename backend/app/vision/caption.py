import logging
from typing import List, Optional
from app.vision.schemas import CaptionResult, ImageAnalysisResult, OCRResult

logger = logging.getLogger("harika.vision.caption")


class CaptionEngine:
    """Generates concise image summaries, captions, and memory indexing tags."""

    def generate_caption(
        self,
        filename: str,
        mime_type: str,
        analysis: Optional[ImageAnalysisResult] = None,
        ocr: Optional[OCRResult] = None
    ) -> CaptionResult:
        category = analysis.classification if analysis else "visual asset"
        summary_prefix = f"Visual {category} '{filename}'"

        tags = ["multimodal", category, mime_type.split('/')[-1]]
        if ocr and ocr.word_count > 0:
            tags.append("text_rich")

        caption = f"{summary_prefix} containing {analysis.description if analysis else 'visual elements'}."
        detailed = (
            f"{caption} Extracted {ocr.word_count if ocr else 0} words of text. "
            f"Detected components: {', '.join(analysis.detected_objects) if analysis else 'generic visual components'}."
        )

        return CaptionResult(
            caption=caption,
            detailed_summary=detailed,
            tags=tags
        )


caption_engine = CaptionEngine()
