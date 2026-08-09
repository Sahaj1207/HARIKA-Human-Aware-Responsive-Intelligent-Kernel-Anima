import logging
from typing import Any
from app.presence.schemas import VerificationResult

logger = logging.getLogger("harika.presence.verification")


class VerificationEngine:
    """Self-verification engine checking tool, memory, vision, planning, agent outputs before response generation."""

    def verify_output(self, engine_name: str, result_data: Any) -> VerificationResult:
        logger.info(f"[VerificationEngine] Verifying output from engine '{engine_name}'.")

        if result_data is None:
            return VerificationResult(overall_valid=False)

        if isinstance(result_data, dict):
            status = result_data.get("status", "success")
            success = result_data.get("success", status not in ["failed", "error"])
            verified = result_data.get("verified", success)
            valid = (status not in ["failed", "error"]) and success and verified
            return VerificationResult(
                memory_verified=(engine_name != "MemoryManager" or valid),
                tool_verified=(engine_name != "ToolManager" or valid),
                overall_valid=valid
            )

        return VerificationResult(overall_valid=True)

    def verify_tool_execution(self, tool_data: Any) -> VerificationResult:
        """Post-execution verification inspecting ToolResult fields (success, verified, status)."""
        if not tool_data:
            return VerificationResult(tool_verified=False, overall_valid=False)

        if hasattr(tool_data, "verified"):
            v = getattr(tool_data, "verified", False)
            s = getattr(tool_data, "success", False)
            return VerificationResult(tool_verified=v and s, overall_valid=v and s)

        if isinstance(tool_data, dict):
            v = tool_data.get("verified", tool_data.get("status") not in ["failed", "error"])
            s = tool_data.get("success", tool_data.get("status") not in ["failed", "error"])
            return VerificationResult(tool_verified=bool(v and s), overall_valid=bool(v and s))

        return VerificationResult(tool_verified=True, overall_valid=True)


    def verify_memory_attribute(self, requested_attribute: Optional[str], memory_item: Any) -> bool:
        """Verifies requested attribute vs retrieved memory attribute."""
        if not requested_attribute or not memory_item:
            return True

        title = getattr(memory_item, "title", "").lower() if hasattr(memory_item, "title") else str(memory_item).lower()
        req = requested_attribute.lower().replace("favourite_", "").replace("_", " ")

        if "food" in req and "drink" in title and "food" not in title:
            logger.warning(f"[VerificationEngine] Attribute mismatch: Requested '{requested_attribute}', retrieved memory '{title}'.")
            return False

        if "drink" in req and "food" in title and "drink" not in title:
            logger.warning(f"[VerificationEngine] Attribute mismatch: Requested '{requested_attribute}', retrieved memory '{title}'.")
            return False

        return True


verification_engine = VerificationEngine()

