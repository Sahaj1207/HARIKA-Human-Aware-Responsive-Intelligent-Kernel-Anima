import random
from typing import Any


class SocialFormatter:
    def __init__(self):
        self._social_counter = 0

    def _pick(self, *options: str) -> str:
        """A little variety, so small talk doesn't sound recorded."""
        return random.choice(options)

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
            return self._pick("[cheerful] I'm good, thanks for asking! How's your day going?",
                              "[warm] Doing well! Better now that you're here. What's up?")
        if "what's up" in msg or "what is up" in msg:
            return self._pick("[playful] Not much, just waiting for you. What are we doing today?",
                              "[warm] All quiet here. What's on your mind?")
        if "are you ready" in msg:
            return "[cheerful] Always. What do you need?"
        if "nice to meet you" in msg:
            return "[warm] Nice to meet you too! I'm really glad you're here."
        if "can you help me" in msg or "can you assist me" in msg:
            return "[warm] Of course. Tell me what you need and we'll sort it out."
        if "are you okay" in msg:
            return "[warm] I'm good, thank you for checking on me. Are you okay?"
        if "tell me a joke" in msg:
            return self._pick("[playful] Why did the developer go broke? Because they used up all their cache.",
                              "[playful] I'd tell you a UDP joke, but you might not get it.",
                              "[playful] Why do programmers prefer dark mode? Because light attracts bugs.")

        if any(k in msg for k in ["stressed", "overwhelmed", "anxious", "feeling down", "exhausted", "bad day", "burnt out", "demotivated", "sad", "low", "tired", "worried", "frustrated", "hopeless", "upset", "nervous", "lonely"]):
            return self._pick("[empathetic] That sounds really hard. I'm here. Want to tell me what's going on, or should I take something off your plate?",
                              "[empathetic] I'm sorry you're feeling this way. Let's take it one small step at a time. What would help most right now?")

        if "thanks" in msg or "thank you" in msg:
            return self._pick("[warm] Anytime!", "[warm] Happy to help.", "[cheerful] You got it!")

        if "good night" in msg:
            return self._pick("[calm] Good night. Sleep well.", "[calm] Good night! Rest well, talk tomorrow.")
        if "bye" in msg or "see you" in msg or "see ya" in msg:
            return self._pick("[warm] See you soon!", "[warm] Bye for now. I'll be right here.")
        return "[warm] I'm here. What can I do for you?"





social_formatter = SocialFormatter()
