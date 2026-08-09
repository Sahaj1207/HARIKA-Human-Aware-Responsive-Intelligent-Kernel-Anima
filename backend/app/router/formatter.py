import logging
from typing import Any, Dict, Tuple
from app.router.schemas import IntentType

logger = logging.getLogger("harika.router.formatter")


class ResponseFormatter:
    """Decides whether LLM is required to format engine output into natural language."""

    def format_response(self, intent: IntentType, result_data: Any, raw_query: str) -> Tuple[str, str]:
        """Returns (formatted_text, formatter_method_name)."""

        # 1. Calculator / Tool result
        if intent == IntentType.TOOL_EXECUTION:
            if isinstance(result_data, dict):
                inner_res = result_data.get("result")
                if isinstance(inner_res, dict) and "result" in inner_res:
                    res_val = inner_res["result"]
                    expr = inner_res.get("expression", raw_query)
                    formatted = f"{expr} = {res_val}"
                    logger.info(f"[ResponseFormatter] Formatted tool result directly without LLM: '{formatted}'.")
                    return formatted, "direct_tool_result"
                elif inner_res is not None:
                    formatted = f"{raw_query} = {inner_res}"
                    logger.info(f"[ResponseFormatter] Formatted tool result directly without LLM: '{formatted}'.")
                    return formatted, "direct_tool_result"


        # 2. Memory Retrieval / Query
        if intent == IntentType.MEMORY_QUERY:
            if isinstance(result_data, list):
                if not result_data:
                    return "I couldn't find any matching memories stored.", "direct_memory_empty"
                titles = [m.title if hasattr(m, 'title') else str(m) for m in result_data]
                formatted = f"Found memory: {', '.join(titles)}"
                logger.info(f"[ResponseFormatter] Formatted memory result directly without LLM.")
                return formatted, "direct_memory_result"

        # 3. Memory Store
        if intent == IntentType.MEMORY_STORE:
            return "Got it! I have saved that in your long-term memory.", "direct_memory_stored"

        # 4. Agent Start / Continue
        if intent in [IntentType.AGENT_START, IntentType.AGENT_CONTINUE]:
            status = result_data.get("status") if isinstance(result_data, dict) else "started"
            return f"Agent goal execution {status}.", "direct_agent_result"

        # Default string fallback
        if isinstance(result_data, str):
            return result_data, "direct_string"

        if isinstance(result_data, dict) and "response" in result_data:
            return result_data["response"], "llm_formatted"

        return str(result_data), "direct_repr"


response_formatter = ResponseFormatter()
