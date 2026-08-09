from typing import Any


def format_greeting_response(engine_output: Any = None, raw_message: str = "") -> str:
    msg = (raw_message or (engine_output.get("message", "") if isinstance(engine_output, dict) else str(engine_output or ""))).lower()
    if "morning" in msg:
        return "Good morning! Ready whenever you are."
    if "afternoon" in msg:
        return "Good afternoon! Ready to assist."
    if "evening" in msg:
        return "Good evening! Ready to help."
    if any(k in msg for k in ["hi", "hey"]):
        return "Hi! What would you like to work on today?"
    return "Hello, Sahaj. Good to see you."




