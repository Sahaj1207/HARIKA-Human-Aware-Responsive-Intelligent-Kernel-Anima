from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.cognition.personality import default_personality, PersonalityProfile
from app.memory.models import MemoryItem, MemoryCategory
from app.tools.result import ToolResult
from app.planning.schemas import Goal, Task, Decision, Reflection


def _abilities() -> str:
    from app.presence.communication.capability import describe_abilities
    return describe_abilities().split(" Just ask")[0]


class ContextBuilder:
    """Dynamically constructs system prompts enriched with structured memory, tool outcomes, and planning decisions."""

    @staticmethod
    def build_system_prompt(
        user_name: Optional[str] = "User",
        personality: Optional[PersonalityProfile] = None,
        memories: Optional[List[MemoryItem]] = None,
        tool_result: Optional[ToolResult] = None,
        decision: Optional[Decision] = None,
        active_goal: Optional[Goal] = None,
        recent_reflection: Optional[Reflection] = None
    ) -> str:
        active_personality = personality or default_personality
        now_local = datetime.now().astimezone().strftime("%A %d %B %Y, %H:%M (%Z)")

        # Base System Directive
        prompt_parts = [
            "You are HARIKA, a warm and capable personal assistant that lives on the user's computer.",
            f"User Name: {user_name if user_name else 'User'}",
            f"Local time: {now_local}\n",
            active_personality.get_instructions(),
            "\nWhat you can do on this computer (through your actions; never say you can't): "
            + _abilities() + " When someone asks for one of these, it is being handled; don't claim you can't see the "
            "screen, set reminders, or act on the computer.",
        ]

        # Inject Decision Engine Strategy
        if decision:
            prompt_parts.append("\n## HARIKA Reflection & Decision Engine Strategy:")
            prompt_parts.append(f"- Selected Strategy: {decision.strategy.value}")
            prompt_parts.append(f"- Decision Confidence: {decision.confidence}")
            prompt_parts.append(f"- Strategy Rationale: {decision.reason}")

        # Inject Active Goal Context
        if active_goal:
            prompt_parts.append("\n## Active Goal:")
            prompt_parts.append(f"- Goal: {active_goal.title} (Priority: {active_goal.priority.value})")
            if active_goal.description:
                prompt_parts.append(f"- Description: {active_goal.description}")

        # Inject Tool Execution Result if present
        if tool_result:
            prompt_parts.append("\n## HARIKA Real-World Action Engine Execution Outcome:")
            prompt_parts.append(f"- Executed Tool: {tool_result.tool_name} (Status: {tool_result.status_code.value})")
            prompt_parts.append(f"- Execution Time: {tool_result.execution_time_ms}ms")
            if tool_result.success:
                prompt_parts.append(f"- Result Output: {tool_result.output}")
            else:
                prompt_parts.append(f"- Execution Error: {tool_result.error}")
            prompt_parts.append("\nDirective: State the tool outcome naturally, accurately, and concisely to the user.")

        # Inject Structured Memory Context if present
        if memories:
            categories_map = {
                "User Profile": [m for m in memories if m.category == MemoryCategory.USER_PROFILE],
                "Active Projects": [m for m in memories if m.category == MemoryCategory.PROJECTS],
                "Current Goals": [m for m in memories if m.category == MemoryCategory.GOALS],
                "User Preferences": [m for m in memories if m.category == MemoryCategory.PREFERENCES],
                "People in Their Life": [m for m in memories if m.category == MemoryCategory.RELATIONSHIPS],
                "Things They Asked You to Remember": [m for m in memories if m.category == MemoryCategory.NOTES],
                "Recent Episodes": [m for m in memories if m.category == MemoryCategory.EPISODES],
            }

            memory_sections = []
            for section_title, items in categories_map.items():
                if items:
                    section_lines = [f"### {section_title}:"]
                    for item in items:
                        same = item.title.strip().lower() == item.content.strip().lower()
                        section_lines.append(f"- {item.content}" if same else f"- {item.title}: {item.content}")
                    memory_sections.append("\n".join(section_lines))

            if memory_sections:
                prompt_parts.append("\n## HARIKA Persistent Knowledge Memory Context:")
                prompt_parts.extend(memory_sections)

        # Inject Recent Reflection Context if present
        if recent_reflection:
            prompt_parts.append("\n## Recent Interaction Reflection:")
            prompt_parts.append(f"- Summary: {recent_reflection.summary}")
            prompt_parts.append(f"- Recommendation: {recent_reflection.next_recommendation}")

        # Last line on purpose: small models follow the final instruction most reliably.
        prompt_parts.append(
            "\nRespond naturally, concisely, and helpfully based on the above context, "
            "in plain sentences with no emoji and no Markdown."
        )
        return "\n".join(prompt_parts)
