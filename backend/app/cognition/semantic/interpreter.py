import asyncio
import json
import re
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.cognition.semantic.catalog import CapabilityCatalog
from app.cognition.semantic.contract import MinimalSemanticIntent, SemanticRequest


class SemanticInterpretationError(ValueError):
    """The provider response cannot safely become a semantic request."""


class LLMResponseProvider(ABC):
    """Minimal adapter over HARIKA's existing async LLM provider contract."""

    @abstractmethod
    async def generate_response(self, messages, system_prompt):
        raise NotImplementedError


class SemanticInterpreter:
    """Interprets language only; it cannot execute or invoke capabilities."""

    def __init__(self, provider: LLMResponseProvider, catalog: CapabilityCatalog, timeout_seconds: float = 10.0):
        self.provider = provider
        self.catalog = catalog
        self.timeout_seconds = timeout_seconds

    async def interpret(self, raw_text: str, context: Optional[Any] = None) -> SemanticRequest:
        prompt = self._build_prompt(context)
        try:
            result = await asyncio.wait_for(
                self.provider.generate_response(
                    messages=[{"role": "user", "content": raw_text}],
                    system_prompt=prompt,
                ),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise SemanticInterpretationError(
                f"LLM semantic interpretation timed out after {self.timeout_seconds:.2f}s."
            ) from exc
        response = result.get("response") if isinstance(result, dict) else None
        payload = self._parse_json(response)
        self._reject_unsafe_payload(payload)
        try:
            intent = MinimalSemanticIntent.model_validate(payload)
        except Exception as exc:
            raise SemanticInterpretationError(f"Invalid minimal semantic intent: {exc}") from exc
        return self._normalize_intent(raw_text, intent)

    def interpret_sync(self, raw_text: str, context: Optional[Any] = None) -> SemanticRequest:
        """Bridge async providers for the current synchronous CognitiveCore API."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.interpret(raw_text, context))

        result: Dict[str, Any] = {}
        error: Dict[str, BaseException] = {}

        def runner():
            try:
                result["value"] = asyncio.run(self.interpret(raw_text, context))
            except BaseException as exc:  # re-raise in caller thread
                error["value"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "value" in error:
            raise error["value"]
        return result["value"]

    def _build_prompt(self, context: Optional[Any]) -> str:
        return (
            "You are HARIKA's semantic interpreter. Return STRICT JSON only with exactly "
            "these four keys: goal, operation, target, parameters. The target is plain "
            "natural language, never a capability ID. Do not output confidence, ambiguity, "
            "constraints, context references, permissions, verification data, ActionGraphs, "
            "shell commands, Python, executable paths, or tool calls. Use normalized values: "
            "launch_application/open/calculator for calculator launch requests; "
            "media_playback/play/YouTube with parameters {query: song} for song playback. "
            "Understand natural variations such as 'bring up', 'start', 'I need', and "
            "'calci' without returning aliases or capability IDs. Examples:\n"
            "open calculator -> {goal: launch_application, operation: open, target: calculator, parameters: {}}\n"
            "open calci -> {goal: launch_application, operation: open, target: calculator, parameters: {}}\n"
            "play a song on YouTube -> {goal: media_playback, operation: play, target: YouTube, parameters: {query: song}}"
        )

    def _normalize_intent(self, raw_text: str, intent: MinimalSemanticIntent) -> SemanticRequest:
        entry, canonical_target = self.catalog.resolve_intent(
            intent.goal,
            intent.operation,
            intent.target,
        )
        entities = dict(intent.parameters)
        if intent.target is not None:
            entities["target"] = canonical_target or intent.target
        if entry is None:
            return SemanticRequest(
                raw_text=raw_text,
                probable_goal=intent.goal,
                operation=intent.operation,
                entities=entities,
                candidate_capabilities=[],
                confidence=0.0,
                ambiguity=["unresolved_capability"],
                clarification_question="I could not match that request to a registered capability.",
                validation_error="No registered capability matched the semantic intent.",
            )
        return SemanticRequest(
            raw_text=raw_text,
            probable_goal=intent.goal,
            operation=intent.operation,
            entities=entities,
            candidate_capabilities=[entry.capability_id],
            confidence=0.95,
            ambiguity=[],
            clarification_question=None,
        )

    @staticmethod
    def _parse_json(response: Any) -> Dict[str, Any]:
        if not isinstance(response, str):
            raise SemanticInterpretationError("LLM semantic response was not text JSON.")
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise SemanticInterpretationError("LLM semantic response was malformed JSON.") from exc
        if not isinstance(payload, dict):
            raise SemanticInterpretationError("LLM semantic response must be a JSON object.")
        return payload

    @classmethod
    def _reject_unsafe_payload(cls, payload: Any) -> None:
        forbidden_keys = {"command", "shell", "script", "python", "code", "executable", "tool_call"}
        suspicious = re.compile(r"(?:subprocess|os\.system|powershell|cmd\.exe|python\s+-|&&|\|\||;)", re.I)

        def walk(value: Any, key: Optional[str] = None):
            if key and key.lower() in forbidden_keys:
                raise SemanticInterpretationError(f"Unsafe execution field '{key}' rejected.")
            if isinstance(value, dict):
                for child_key, child in value.items():
                    walk(child, str(child_key))
            elif isinstance(value, list):
                for child in value:
                    walk(child, key)
            elif isinstance(value, str) and suspicious.search(value):
                raise SemanticInterpretationError("Potential executable command content rejected.")

        walk(payload)


def default_semantic_interpreter() -> SemanticInterpreter:
    from app.cognition.manager import CognitionManager
    from app.router.registry import router_registry
    from app.tools.manager import tool_manager
    from app.presence.capability_manager import capability_manager

    provider = CognitionManager().get_provider()
    catalog = CapabilityCatalog.from_sources(
        tool_registry=tool_manager.registry,
        router_registry=router_registry,
        capability_manager=capability_manager,
    )
    return SemanticInterpreter(provider=provider, catalog=catalog)
