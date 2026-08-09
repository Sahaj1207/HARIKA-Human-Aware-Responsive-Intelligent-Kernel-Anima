import logging
from typing import Any

logger = logging.getLogger("harika.presence.communication.memory")


def format_memory_response(intent: str, engine_output: Any, raw_message: str = "") -> str:
    clean = raw_message.lower().strip() if raw_message else ""
    if intent == "MEMORY_STORE":
        if isinstance(engine_output, dict) and engine_output.get("status") == "updated":
            val = engine_output.get("value", "")
            if val:
                return f"Got it. I've updated that for you — your preference is now set to {val}."
        if clean and (clean.startswith("no ") or clean.startswith("no,") or clean.startswith("no.") or any(k in clean for k in ["i meant ", "that's wrong", "i like"])):
            val = clean.replace("no.", "").replace("no,", "").replace("no ", "").replace("i meant", "").replace("i like", "").replace("now", "").replace("my favourite food is", "").replace("my favourite drink is", "").strip()
            if val:
                return f"Got it. I've updated that for you — your preference is now set to {val}."
        return "I'll remember that."


    if intent in ["MEMORY_QUERY", "MEMORY_UPDATE"] or (isinstance(engine_output, list) and engine_output) or (isinstance(engine_output, dict) and engine_output.get("status") == "context_query"):
        if isinstance(engine_output, dict) and engine_output.get("status") == "context_query":
            return engine_output.get("summary", "We are currently in an active conversation session.")
        if isinstance(engine_output, list) and len(engine_output) > 0:

            top = engine_output[0]
            title = top.title if hasattr(top, 'title') else (top.get("title") if isinstance(top, dict) else str(top))
            val = title.replace("User Fact: ", "").replace("user ", "").strip()
            if " is " in val:
                parts = val.split(" is ")
                attr_name = parts[0].replace("favourite_", "").replace("_", " ").strip()
                val_str = parts[1].strip()
                if val_str:
                    return f"Your favourite {attr_name} is {val_str}."
            return f"I remember you mentioned: {val}."

        q = (engine_output.get("query", "") if isinstance(engine_output, dict) else "").lower()
        if "food" in q:
            return "I don't think you've told me your favourite food yet."
        elif "drink" in q:
            return "I don't think you've told me your favourite drink yet."
        return "I don't seem to have a record of that yet."


    return "I'll remember that."

