import re
from typing import Any, Optional
from app.presence.schemas import ExperienceDecision

# Pictographic emoji, variation selectors and joiners. The chat renders plain
# text, and small models don't always honour "no emoji" in the prompt.
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]+")


def plain_text(text: str) -> str:
    """A model reply as clean plain text for the chat."""
    text = _EMOJI.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"[ \t]+([.,!?])", r"\1", text)).strip()


def format_chat_response(intent: str, engine_output: Any, experience: Optional[ExperienceDecision] = None) -> str:
    message = engine_output.get("message", "").lower() if isinstance(engine_output, dict) else ""
    if isinstance(engine_output, dict) and engine_output.get("cognitive_goal") == "conversation_or_entertainment":
        return "You could listen to something relaxing, watch something interesting, or just chat. What sounds good?"
    if isinstance(engine_output, dict) and engine_output.get("cognitive_goal") == "advice_or_exploration":
        return "We can explore a few options together. Tell me what kind of time, energy, or outcome you have in mind."
    if message:
        if "good morning" in message:
            return "Good morning! How can I help today?"
        if "good afternoon" in message:
            return "Good afternoon! How can I help today?"
        if "good evening" in message:
            return "Good evening! How can I help today?"
        if message.startswith("hi") or message.startswith("hey"):
            return "Hi! How can I help today?"
        if message.startswith("hello") or message.startswith("greetings"):
            return "Hello! How can I help today?"
        if "how are you" in message or "how's it going" in message or "how is it going" in message:
            return "I'm doing well, thank you for asking! How can I help today?"
        if "what's up" in message or "what is up" in message:
            return "Not much! Ready to help with your tasks—what would you like to work on?"
        if "what can you help me with" in message or "can you help me" in message or "can you assist me" in message:
            return "I can assist with memory, desktop tools, web tools, planning, and everyday questions."

    if experience and experience.decision == "offer_diagnostics":
        return "I noticed repeated build failures. Shall I inspect the logs to help diagnose the issue?"
    elif experience and experience.decision == "offer_rehearsal":
        return "Good luck with your presentation tomorrow! Would you like to rehearse with a quick mock Q&A session?"

    # A generated answer from the cognition engine is the response; don't replace it with a template.
    if isinstance(engine_output, dict) and isinstance(engine_output.get("response"), str) and engine_output["response"].strip():
        return plain_text(engine_output["response"])

    if intent == "UNKNOWN_INTENT":
        return "I'm not sure how to assist with that directive. Could you please rephrase?"

    if intent == "CLARIFICATION":
        return "Could you clarify what you'd like me to do?"

    if intent == "ERROR":
        return "I encountered an error processing your request."

    if isinstance(engine_output, str) and engine_output.strip():
        return engine_output

    return "I'm here to assist you with your request."

