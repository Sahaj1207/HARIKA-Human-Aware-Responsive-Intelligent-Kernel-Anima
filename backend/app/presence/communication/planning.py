from typing import Any


def format_planning_response(intent: str, engine_output: Any) -> str:
    if intent == "AGENT_START":
        return "Started autonomous agent task."
    if intent == "AGENT_CONTINUE":
        return "Continuing agent execution."
    if intent == "PLAN_QUERY" or (isinstance(engine_output, dict) and engine_output.get("status") == "plan_query"):
        if isinstance(engine_output, dict) and "summary" in engine_output:
            return engine_output["summary"]
        return "Here is your active plan."
    return "Plan created successfully."

