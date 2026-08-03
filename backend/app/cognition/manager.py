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


class CognitionManager:
    """Central Manager orchestrating Memory Retrieval, LLM Provider selection, Context Building, and Inference."""

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
        conversation_history: Optional[List[Dict[str, str]]] = None,
        provider_name: Optional[str] = None,
        personality: Optional[PersonalityProfile] = None
    ) -> Dict[str, Any]:
        # 1. Retrieve top 10 relevant persistent memories for prompt injection
        retrieved_memories = memory_manager.get_memories(query=message, user_id="default")

        # 2. Select active LLM Provider
        provider = self.get_provider(provider_name)

        # 3. Build Context & Enriched System Prompt
        system_prompt = ContextBuilder.build_system_prompt(
            user_name=user_name,
            personality=personality or default_personality,
            memories=retrieved_memories
        )

        # 4. Assemble message history
        history = list(conversation_history or [])
        history.append({"role": "user", "sender": "user", "content": message})

        # 5. Generate Response via Provider
        result = await provider.generate_response(
            messages=history,
            system_prompt=system_prompt
        )

        # 6. Non-blocking Asynchronous Memory Extraction & Storage Pipeline
        memory_manager.process_conversation_async(
            user_message=message,
            assistant_response=result.get("response", ""),
            user_id="default"
        )

        return result


cognition_manager = CognitionManager()
