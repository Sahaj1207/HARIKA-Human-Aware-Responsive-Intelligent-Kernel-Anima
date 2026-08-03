from datetime import datetime, timezone
from typing import Optional, List
from app.cognition.personality import default_personality, PersonalityProfile
from app.memory.models import MemoryItem, MemoryCategory


class ContextBuilder:
    """Dynamically constructs system prompts enriched with structured memory sections."""

    @staticmethod
    def build_system_prompt(
        user_name: Optional[str] = "User",
        personality: Optional[PersonalityProfile] = None,
        memories: Optional[List[MemoryItem]] = None
    ) -> str:
        active_personality = personality or default_personality
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Base OS System Directive
        prompt_parts = [
            "You are HARIKA, a futuristic AI Operating System with a cinematic 3D core.",
            f"User Name: {user_name if user_name else 'User'}",
            f"Current Timestamp: {now_utc}\n",
            active_personality.get_instructions()
        ]

        # Inject Structured Memory Context if present
        if memories:
            categories_map = {
                "User Profile": [m for m in memories if m.category == MemoryCategory.USER_PROFILE],
                "Active Projects": [m for m in memories if m.category == MemoryCategory.PROJECTS],
                "Current Goals": [m for m in memories if m.category == MemoryCategory.GOALS],
                "User Preferences": [m for m in memories if m.category == MemoryCategory.PREFERENCES],
                "Recent Episodes": [m for m in memories if m.category == MemoryCategory.EPISODES],
            }

            memory_sections = []
            for section_title, items in categories_map.items():
                if items:
                    section_lines = [f"### {section_title}:"]
                    for item in items:
                        section_lines.append(f"- {item.title}: {item.content}")
                    memory_sections.append("\n".join(section_lines))

            if memory_sections:
                prompt_parts.append("\n## HARIKA Persistent Knowledge Memory Context:")
                prompt_parts.extend(memory_sections)

        prompt_parts.append("\nRespond naturally, concisely, and helpfully based on the above context.")
        return "\n".join(prompt_parts)
