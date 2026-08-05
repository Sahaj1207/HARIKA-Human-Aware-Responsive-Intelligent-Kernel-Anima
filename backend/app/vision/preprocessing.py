import os
import re
import logging
from typing import Tuple

logger = logging.getLogger("harika.vision.preprocessing")

# Security constants
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
SUPPORTED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
SUPPORTED_PDF_MIMES = {"application/pdf"}
SUPPORTED_MIMES = SUPPORTED_IMAGE_MIMES | SUPPORTED_PDF_MIMES
FORBIDDEN_EXTENSIONS = {".exe", ".bat", ".sh", ".cmd", ".msi", ".dll", ".so", ".py", ".js", ".vbs", ".ps1"}


class SecurityValidationError(ValueError):
    """Raised when a file fails security or MIME validation."""
    pass


class VisionPreprocessor:
    """Handles file validation, size checks, executable rejection, and filename sanitization."""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes user-provided filenames to prevent path traversal or invalid characters."""
        clean = os.path.basename(filename)
        clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', clean)
        return clean or "uploaded_file"

    @staticmethod
    def validate_file(file_bytes: bytes, filename: str, content_type: str) -> Tuple[str, str]:
        """Validates file size, extension, and MIME type."""
        # 1. Size check
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise SecurityValidationError(f"File size ({len(file_bytes)} bytes) exceeds maximum limit of {MAX_FILE_SIZE_BYTES} bytes (15 MB).")

        if len(file_bytes) == 0:
            raise SecurityValidationError("File is empty.")

        # 2. Extension check
        clean_name = VisionPreprocessor.sanitize_filename(filename)
        _, ext = os.path.splitext(clean_name.lower())
        if ext in FORBIDDEN_EXTENSIONS:
            raise SecurityValidationError(f"Forbidden executable file extension '{ext}'. Upload rejected.")

        # 3. Magic Bytes / Header check
        mime = content_type.lower()
        if file_bytes.startswith(b"%PDF"):
            mime = "application/pdf"
        elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif file_bytes.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
            mime = "image/webp"

        if mime not in SUPPORTED_MIMES:
            raise SecurityValidationError(f"Unsupported file type '{mime}'. Allowed types: PNG, JPG, WEBP, PDF.")

        logger.info(f"[VisionPreprocessor] Validated asset '{clean_name}' ({mime}, {len(file_bytes)} bytes).")
        return clean_name, mime


vision_preprocessor = VisionPreprocessor()
