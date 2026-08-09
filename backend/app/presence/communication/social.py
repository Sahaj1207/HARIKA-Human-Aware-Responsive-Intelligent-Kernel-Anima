from typing import Any


class SocialFormatter:
    def __init__(self):
        self._social_counter = 0

    def format_social_response(self, engine_output: Any = None, raw_message: str = "") -> str:
        self._social_counter += 1
        msg = (raw_message or (engine_output.get("message", "") if isinstance(engine_output, dict) else str(engine_output or ""))).lower()

        if any(k in msg for k in ["tell me about yourself"]):
            return "I am HARIKA, an autonomous AI assistant built by Sahaj to assist with task execution, memory management, and system workflows."
        if any(k in msg for k in ["who created", "who built", "who made", "who developed", "creator"]):
            return "I was created by Sahaj."
        if any(k in msg for k in ["who are you", "what is your name"]):
            return "I am HARIKA, your AI assistant created by Sahaj."

        if "how are you" in msg or "how's it going" in msg or "how is it going" in msg:
            variations = [
                "I'm doing well, thank you for asking!",
                "I'm functioning smoothly and ready for your next directive.",
                "All systems operational and ready to assist."
            ]
            return variations[self._social_counter % len(variations)]
        if "what's up" in msg or "what is up" in msg:
            return "Not much! Ready to assist you with your tasks."
        if "are you ready" in msg:
            return "All systems are ready for your directives."
        if "nice to meet you" in msg:
            return "Nice to meet you as well! Ready to help."
        if "can you help me" in msg or "can you assist me" in msg:
            return "Absolutely! I can assist with memory, desktop tools, web tools, and planning."
        if "are you okay" in msg:
            return "I'm functioning smoothly and ready to help!"

        if any(k in msg for k in ["stressed", "overwhelmed", "anxious", "feeling down", "exhausted", "bad day", "burnt out", "demotivated", "sad", "low", "tired", "worried", "frustrated", "hopeless", "upset", "nervous", "lonely"]):
            return "I'm really sorry to hear you're feeling that way. Take a deep breath and take things one step at a time. I'm right here if you need support or assistance."

        if "thanks" in msg or "thank you" in msg:
            return "You're welcome!"

        if "good night" in msg:
            return "Good night! Rest well."
        if "bye" in msg or "see you" in msg or "see ya" in msg:
            return "See you later."
        return "I'm here and ready to help!"





social_formatter = SocialFormatter()
