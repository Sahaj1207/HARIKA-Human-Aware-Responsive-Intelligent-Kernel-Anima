from typing import Dict, Any


class PersonalityProfile:
    """Defines HARIKA's behavioral directives and tone of voice."""

    def __init__(self, name: str = "default", traits: Dict[str, Any] = None):
        self.name = name
        self.traits = traits or {
            "tone": "Friendly, Professional, Helpful, Concise",
            "style": "Direct, elegant, informative, free of unnecessary fluff",
            "persona": "Cinematic AI Operating System Intelligence"
        }

    def get_instructions(self) -> str:
        return (
            f"Personality Directives ({self.name}):\n"
            f"- Tone: {self.traits['tone']}\n"
            f"- Style: {self.traits['style']}\n"
            f"- Persona: {self.traits['persona']}\n"
            "- Always address the user politely and keep responses clear and concise."
        )


# Default System Personality Instance
default_personality = PersonalityProfile()
