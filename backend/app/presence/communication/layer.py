import logging
from typing import Any, Optional
from app.presence.schemas import ExperienceDecision
from app.presence.communication.greeting import format_greeting_response
from app.presence.communication.social import social_formatter
from app.presence.communication.capability import format_capability_response
from app.presence.communication.tool import format_tool_response
from app.presence.communication.memory import format_memory_response
from app.presence.communication.planning import format_planning_response
from app.presence.communication.chat import format_chat_response

logger = logging.getLogger("harika.presence.communication.layer")


class CommunicationLayer:
    """The ONLY component authorized to generate natural language phrasing for subsystem results (Dispatcher)."""

    def format_human_response(
        self,
        intent: str,
        engine_output: Any,
        raw_message: str,
        experience: Optional[ExperienceDecision] = None
    ) -> str:
        if intent == "GREETING":
            return format_greeting_response(engine_output, raw_message)

        if intent == "CAPABILITY_QUERY":
            return format_capability_response(engine_output, raw_message)

        if intent == "SOCIAL_CONVERSATION":
            return social_formatter.format_social_response(engine_output, raw_message)

        if intent in ["TOOL_EXECUTION", "EXECUTION_FEEDBACK"]:
            return format_tool_response(intent, engine_output, raw_message)

        if intent in ["MEMORY_STORE", "MEMORY_QUERY", "MEMORY_UPDATE"]:
            return format_memory_response(intent, engine_output, raw_message)

        if intent in ["PLAN_CREATION", "PLAN_QUERY", "AGENT_START", "AGENT_CONTINUE"]:
            return format_planning_response(intent, engine_output)

        return format_chat_response(intent, engine_output, experience)




communication_layer = CommunicationLayer()
