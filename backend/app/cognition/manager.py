import asyncio
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger
from app.cognition.base_provider import BaseLLMProvider
from app.cognition.context_builder import ContextBuilder
from app.cognition.personality import default_personality, PersonalityProfile
from app.cognition.providers.ollama_provider import OllamaProvider
from app.cognition.providers.openai_provider import OpenAIProvider
from app.cognition.providers.gemini_provider import GeminiProvider
from app.cognition.providers.groq_provider import GroqProvider
from app.cognition.providers.claude_provider import ClaudeProvider
from app.memory.manager import memory_manager
from app.tools.manager import tool_manager
from app.tools.result import ToolResult
from app.planning.manager import planning_manager


class CognitionManager:
    """Central Manager orchestrating Memory Retrieval, Planning Engine, Tool Execution, LLM Inference, and Post-Reflection."""

    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {
            "ollama": OllamaProvider(),
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
            "claude": ClaudeProvider(),
        }

    def get_provider(self, provider_name: Optional[str] = None) -> BaseLLMProvider:
        target = (provider_name or settings.DEFAULT_LLM_PROVIDER).lower()
        if target not in self.providers:
            logger.warning(f"Provider '{target}' not found. Falling back to default ('ollama').")
            target = "ollama"
        return self.providers[target]

    async def process_chat(
        self,
        message: str,
        user_name: Optional[str] = "User",
        user_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        provider_name: Optional[str] = None,
        personality: Optional[PersonalityProfile] = None
    ) -> Dict[str, Any]:
        # 1. Retrieve top 10 relevant persistent memories
        scoped_user_id = user_id or user_name or "default"
        retrieved_memories = memory_manager.get_memories(query=message, user_id=scoped_user_id)

        # 2. Action Engine: Plan action
        action_plan = tool_manager.plan_action(message)

        # 3. Planning & Decision Engine Strategy Evaluation
        decision = planning_manager.evaluate_decision(
            user_message=message,
            is_tool_action=action_plan.is_tool_action,
            tool_name=action_plan.actions[0].tool_name if action_plan.actions else None
        )

        active_goals = planning_manager.get_active_goals()
        active_goal = active_goals[0] if active_goals else None

        # 4. Execute tool action if planned
        tool_result: Optional[ToolResult] = None
        if action_plan.is_tool_action:
            tool_result = await tool_manager.execute_planned_action(action_plan)

        # 5. Select active LLM Provider
        provider = self.get_provider(provider_name)

        # 6. Build Context & Enriched System Prompt (Memory + Tool Outcome + Decision + Goal)
        system_prompt = ContextBuilder.build_system_prompt(
            user_name=user_name,
            personality=personality or default_personality,
            memories=retrieved_memories,
            tool_result=tool_result,
            decision=decision,
            active_goal=active_goal
        )

        # 7. Assemble message history
        history = list(conversation_history or [])
        history.append({"role": "user", "sender": "user", "content": message})

        # 8. Generate Response via Provider
        result = await provider.generate_response(
            messages=history,
            system_prompt=system_prompt
        )

        assistant_text = result.get("response", "")

        # 9. Asynchronous Non-blocking Memory Extraction
        memory_manager.process_conversation_async(
            user_message=message,
            assistant_response=assistant_text,
            user_id=scoped_user_id
        )

        # 10. Asynchronous Non-blocking Post-Response Reflection Recording
        asyncio.create_task(
            self._record_reflection_task(
                message=message,
                assistant_response=assistant_text,
                was_tool_used=tool_result is not None,
                tool_name=tool_result.tool_name if tool_result else None,
                success=tool_result.success if tool_result else True
            )
        )

        return result

    async def _record_reflection_task(
        self,
        message: str,
        assistant_response: str,
        was_tool_used: bool,
        tool_name: Optional[str],
        success: bool
    ) -> None:
        try:
            planning_manager.record_reflection(
                user_message=message,
                assistant_response=assistant_response,
                was_tool_used=was_tool_used,
                tool_name=tool_name,
                success=success
            )
        except Exception as e:
            logger.error(f"[CognitionManager] Async reflection recording error: {e}")


cognition_manager = CognitionManager()
