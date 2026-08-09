from typing import Any, Optional
from app.presence.schemas import ExperienceDecision


def format_chat_response(intent: str, engine_output: Any, experience: Optional[ExperienceDecision] = None) -> str:
    if experience and experience.decision == "offer_diagnostics":
        return "I noticed repeated build failures. Shall I inspect the logs to help diagnose the issue?"
    elif experience and experience.decision == "offer_rehearsal":
        return "Good luck with your presentation tomorrow! Would you like to rehearse with a quick mock Q&A session?"

    if intent == "UNKNOWN_INTENT":
        return "I'm not sure how to assist with that directive. Could you please rephrase?"

    if intent == "CLARIFICATION":
        return "Could you clarify what you'd like me to do?"

    if intent == "ERROR":
        return "I encountered an error processing your request."

    if isinstance(engine_output, str) and engine_output.strip():
        return engine_output

    return "I'm here to assist you with your request."

