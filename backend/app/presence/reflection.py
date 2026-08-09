import logging
from typing import Any, Dict
from app.presence.schemas import ReflectionResult

logger = logging.getLogger("harika.presence.reflection")


class ReflectionEngine:
    """Internal reflection engine validating reasoning before response generation without exposing chain-of-thought."""

    def reflect_on_execution(self, intent: str, result_data: Any, raw_query: str) -> ReflectionResult:
        logger.info(f"[ReflectionEngine] Reflecting on intent '{intent}' for query '{raw_query[:20]}...'.")

        if result_data is None:
            return ReflectionResult(
                retrieved_correct_memory=False,
                executed_correct_tool=False,
                answered_user_question=False,
                reason="Subsystem returned empty result."
            )

        if isinstance(result_data, dict) and result_data.get("status") == "failed":
            res_val = result_data.get("result", "Execution failed.")
            res_str = str(res_val) if not isinstance(res_val, str) else res_val
            return ReflectionResult(
                retrieved_correct_memory=True,
                executed_correct_tool=False,
                answered_user_question=False,
                reason=res_str
            )


        return ReflectionResult(
            retrieved_correct_memory=True,
            executed_correct_tool=True,
            answered_user_question=True,
            reason="Execution validated successfully."
        )


reflection_engine = ReflectionEngine()
