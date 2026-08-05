from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class OCRBlock(BaseModel):
    text: str
    category: str = Field(default="text", description="Category: 'text', 'number', 'table', 'code', 'ui'")
    confidence: float = 1.0
    bounding_box: Optional[List[int]] = None


class OCRResult(BaseModel):
    raw_text: str = ""
    blocks: List[OCRBlock] = Field(default_factory=list)
    detected_language: str = "en"
    word_count: int = 0
    latency_ms: float = 0.0


class ImageAnalysisResult(BaseModel):
    classification: str = Field(default="photo", description="photo, screenshot, chart, graph, flowchart, ui, code, diagram")
    description: str = ""
    detected_objects: List[str] = Field(default_factory=list)
    dimensions: Optional[Dict[str, int]] = None
    color_palette: List[str] = Field(default_factory=list)
    confidence: float = 0.90


class PDFPageAnalysis(BaseModel):
    page_number: int
    text: str = ""
    image_count: int = 0
    has_tables: bool = False


class PDFAnalysisResult(BaseModel):
    filename: str
    total_pages: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pages: List[PDFPageAnalysis] = Field(default_factory=list)
    extracted_text: str = ""


class CaptionResult(BaseModel):
    caption: str = ""
    detailed_summary: str = ""
    tags: List[str] = Field(default_factory=list)


class VisionResult(BaseModel):
    id: str
    filename: str
    file_type: str = Field(..., description="image/png, image/jpeg, application/pdf, etc.")
    provider: str
    model: str
    ocr: Optional[OCRResult] = None
    image_analysis: Optional[ImageAnalysisResult] = None
    pdf_analysis: Optional[PDFAnalysisResult] = None
    caption: Optional[CaptionResult] = None
    summary: str = ""
    latency_ms: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VisionHistoryItem(BaseModel):
    id: str
    filename: str
    file_type: str
    provider: str
    model: str
    latency_ms: float
    result_summary: str
    timestamp: str


class VisionMetrics(BaseModel):
    images_analyzed: int = 0
    pdfs_processed: int = 0
    total_ocr_requests: int = 0
    average_ocr_latency_ms: float = 0.0
    average_analysis_time_ms: float = 0.0
    failure_rate_percent: float = 0.0
    provider_usage: Dict[str, int] = Field(default_factory=dict)
