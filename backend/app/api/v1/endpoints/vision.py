from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Header
from app.vision.manager import vision_manager
from app.vision.schemas import VisionResult, OCRResult, VisionMetrics, VisionHistoryItem
from app.vision.preprocessing import SecurityValidationError

router = APIRouter()


@router.post("/image", response_model=VisionResult)
async def process_image(
    file: UploadFile = File(...),
    x_vision_provider: Optional[str] = Header(None, alias="X-Vision-Provider"),
    x_vision_model: Optional[str] = Header(None, alias="X-Vision-Model")
):
    """Processes an image file (PNG, JPG, WEBP) returning structured visual analysis."""
    try:
        content = await file.read()
        return vision_manager.process_image(
            file_bytes=content,
            filename=file.filename or "image.png",
            content_type=file.content_type or "image/png",
            provider_override=x_vision_provider,
            model_override=x_vision_model
        )
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision image processing failed: {str(e)}")


@router.post("/pdf", response_model=VisionResult)
async def process_pdf(
    file: UploadFile = File(...),
    x_vision_provider: Optional[str] = Header(None, alias="X-Vision-Provider"),
    x_vision_model: Optional[str] = Header(None, alias="X-Vision-Model")
):
    """Parses and analyzes a PDF document page-by-page."""
    try:
        content = await file.read()
        return vision_manager.process_pdf(
            file_bytes=content,
            filename=file.filename or "document.pdf",
            content_type=file.content_type or "application/pdf",
            provider_override=x_vision_provider,
            model_override=x_vision_model
        )
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision PDF processing failed: {str(e)}")


@router.post("/ocr", response_model=OCRResult)
async def extract_ocr(
    file: UploadFile = File(...),
    x_vision_provider: Optional[str] = Header(None, alias="X-Vision-Provider")
):
    """Extracts OCR text, blocks, numbers, and code snippets from an uploaded asset."""
    try:
        content = await file.read()
        return vision_manager.extract_ocr(
            file_bytes=content,
            filename=file.filename or "asset",
            content_type=file.content_type or "image/png",
            provider_override=x_vision_provider
        )
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision OCR extraction failed: {str(e)}")


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_vision_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns persistent vision processing history log."""
    return vision_manager.get_history(limit=limit)


@router.get("/metrics", response_model=VisionMetrics)
async def get_vision_metrics():
    """Returns analytics, average latencies, and provider usage metrics."""
    return vision_manager.get_metrics()
