from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLLMProvider(ABC):
    """Abstract Base Class interface for all HARIKA LLM Cognition Providers."""

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str
    ) -> Dict[str, Any]:
        """
        Generates an AI response from the provider.
        
        Returns:
            Dict containing:
                - response (str): Generated message string.
                - provider (str): Provider identifier name.
                - model (str): Active model identifier.
                - latency_ms (int): Execution duration in milliseconds.
        """
        pass
