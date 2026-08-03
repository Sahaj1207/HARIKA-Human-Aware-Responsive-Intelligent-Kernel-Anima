from datetime import datetime, timezone
from typing import Optional
from app.cognition.personality import default_personality, PersonalityProfile


class ContextBuilder:
    """Dynamically constructs system prompts and contextual parameters for LLM requests."""

    @staticmethod
    def build_system_prompt(
        user_name: Optional[str] = "User",
        personality: Optional[PersonalityProfile] = None
    ) -> str:
        active_personality = personality or default_personality
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        prompt = (
            "You are HARIKA, a futuristic AI Operating System with a cinematic 3D core.\n"
            f"User Name: {user_name if user_name else 'User'}\n"
            f"Current Timestamp: {now_utc}\n\n"
            f"{active_personality.get_instructions()}\n\n"
            "Respond naturally, concisely, and helpfully."
        )
        return prompt
