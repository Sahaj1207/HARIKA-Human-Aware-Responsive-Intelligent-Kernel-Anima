import base64
import logging
from typing import Dict, Any, Tuple, Optional
from app.tools.base_tool import BaseTool
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.registry import tool_registry
from app.vision.manager import vision_manager

logger = logging.getLogger("harika.tools.visual_reader")


class VisualReaderTool(BaseTool):
    """Visual Asset & Document Analysis Tool Plugin for the Action Engine."""

    manifest = ToolManifest(
        name="visual_reader",
        display_name="Visual Document Reader",
        description="Analyzes images or PDFs to extract structured OCR text, summary, and visual components.",
        version="1.0.0",
        author="HARIKA OS Vision",
        category="utilities",
        permissions=PermissionLevel.NONE,
        enabled=True,
        platforms=["windows", "linux", "darwin"]
    )
    timeout_seconds = 10.0

    def health_check(self) -> ToolHealth:
        h = vision_manager.health_check()
        return ToolHealth(available=h.get("ready", True), reason="Vision Engine integrated", dependencies=["vision_manager"])

    def validate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        file_bytes_b64 = args.get("file_b64")
        if not file_bytes_b64 or not isinstance(file_bytes_b64, str):
            return False, "Argument 'file_b64' (Base64 encoded string) is required."
        return True, None

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        filename = args.get("filename", "asset.png")
        mime_type = args.get("mime_type", "image/png")
        b64_str = args["file_b64"]

        if dry_run:
            return {
                "dry_run": True,
                "action": "analyze_visual_asset",
                "filename": filename,
                "mime_type": mime_type
            }

        try:
            file_bytes = base64.b64decode(b64_str)
            if mime_type.lower() == "application/pdf" or filename.lower().endswith(".pdf"):
                v_res = vision_manager.process_pdf(file_bytes, filename, mime_type)
            else:
                v_res = vision_manager.process_image(file_bytes, filename, mime_type)

            return {
                "status": "success",
                "filename": v_res.filename,
                "summary": v_res.summary,
                "extracted_text": v_res.ocr.raw_text if v_res.ocr else "",
                "classification": v_res.image_analysis.classification if v_res.image_analysis else "document",
                "provider": v_res.provider,
                "latency_ms": v_res.latency_ms
            }
        except Exception as e:
            logger.error(f"[VisualReaderTool] Execution failed for '{filename}': {e}")
            return {"status": "error", "error": str(e)}


visual_reader_tool = VisualReaderTool()
tool_registry.register_tool(visual_reader_tool)
