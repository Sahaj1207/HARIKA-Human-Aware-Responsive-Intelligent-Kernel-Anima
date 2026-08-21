import asyncio
import json
import unittest

from app.cognition.core import CognitiveCore
from app.cognition.semantic.catalog import CapabilityCatalog
from app.cognition.semantic.contract import MinimalSemanticIntent, SemanticRequest
from app.cognition.semantic.interpreter import (
    LLMResponseProvider,
    SemanticInterpretationError,
    SemanticInterpreter,
)
from app.router.action_graph import ActionGraph, ActionNode
from app.router.schemas import IntentType, RequestContext
from app.tools.base_tool import BaseTool
from app.tools.registry import ToolRegistry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest
from app.tools.planner import ActionPlanner


class FakeApplicationTool(BaseTool):
    manifest = ToolManifest(
        name="open_application",
        display_name="Application Launcher",
        description="Launches installed desktop applications.",
        permissions=PermissionLevel.LOW,
        capabilities=["open_application", "close_application"],
        target_aliases={"calculator": ["calculator", "calc", "cal"]},
    )

    def health_check(self):
        return ToolHealth()

    async def execute(self, args, dry_run=False):
        return {"success": True, "verified": True, "args": args}


class FakeRouterRegistry:
    def get_capabilities(self):
        return []


class StubContextBuilder:
    def build_context(self, message, user_id="default", session_id="default", conversation_history=None):
        return RequestContext(message=message, user_id=user_id, session_id=session_id)


class FakeSemanticInterpreter:
    def __init__(self, request, catalog):
        self.request = request
        self.catalog = catalog

    def interpret_sync(self, raw_text, context):
        return self.request


class FailingSemanticInterpreter:
    def __init__(self, catalog):
        self.catalog = catalog

    def interpret_sync(self, raw_text, context):
        raise SemanticInterpretationError("malformed")


class FallbackClassifier:
    def classify_request(self, context):
        graph = ActionGraph()
        graph.add_node(ActionNode(
            intent=IntentType.CHAT,
            engine="CognitionManager",
            action="process_chat",
            arguments={"message": context.message},
        ))
        return graph, 0.9


class FakeProvider(LLMResponseProvider):
    def __init__(self, payload):
        self.payload = payload

    async def generate_response(self, messages, system_prompt):
        response = self.payload(messages[-1]["content"]) if callable(self.payload) else self.payload
        return {"response": json.dumps(response) if isinstance(response, dict) else response}


class SlowProvider(LLMResponseProvider):
    async def generate_response(self, messages, system_prompt):
        await asyncio.sleep(1.0)
        return {"response": "{}"}


class SemanticUnderstandingTests(unittest.TestCase):
    def make_catalog(self):
        registry = ToolRegistry()
        registry.register_tool(FakeApplicationTool())
        return CapabilityCatalog.from_sources(registry, FakeRouterRegistry())

    def make_interpreter(self, payload):
        return SemanticInterpreter(FakeProvider(payload), self.make_catalog())

    def test_minimal_contract_contains_only_llm_fields(self):
        intent = MinimalSemanticIntent(
            goal="launch_application",
            operation="open",
            target="calculator",
            parameters={},
        )
        self.assertEqual(intent.target, "calculator")
        self.assertEqual(intent.parameters, {})

    def test_calculator_variations_normalize_to_same_capability_without_phrase_aliases(self):
        payload = {
            "goal": "launch_application",
            "operation": "open",
            "target": "calculator",
            "parameters": {},
        }
        for text in (
            "open calculator",
            "bring up the calculator",
            "can you start the calculator",
            "I need the calculator",
        ):
            result = asyncio.run(self.make_interpreter(payload).interpret(text))
            self.assertTrue(result.is_valid)
            self.assertEqual(result.probable_goal, "launch_application")
            self.assertEqual(result.operation, "open")
            self.assertEqual(result.entities["target"], "calculator")
            self.assertEqual(result.candidate_capabilities, ["open_application"])

    def test_calci_can_use_model_canonical_target_without_alias(self):
        result = asyncio.run(self.make_interpreter({
            "goal": "launch_application",
            "operation": "open",
            "target": "calculator",
            "parameters": {},
        }).interpret("open calci"))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.entities["target"], "calculator")
        self.assertEqual(result.candidate_capabilities, ["open_application"])

    def test_media_intent_preserves_minimal_semantics_without_inventing_capability(self):
        result = asyncio.run(self.make_interpreter({
            "goal": "media_playback",
            "operation": "play",
            "target": "YouTube",
            "parameters": {"query": "song"},
        }).interpret("play a song on YouTube"))
        self.assertEqual(result.probable_goal, "media_playback")
        self.assertEqual(result.operation, "play")
        self.assertEqual(result.entities["target"], "YouTube")
        self.assertEqual(result.entities["query"], "song")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.candidate_capabilities, [])

    def test_malformed_json_fails_safely(self):
        with self.assertRaises(SemanticInterpretationError):
            asyncio.run(self.make_interpreter("not json").interpret("open calculator"))

    def test_missing_goal_fails_safely(self):
        with self.assertRaises(SemanticInterpretationError):
            asyncio.run(self.make_interpreter({
                "operation": "open", "target": "calculator", "parameters": {}
            }).interpret("open calculator"))

    def test_llm_capability_id_is_rejected_from_minimal_contract(self):
        with self.assertRaises(SemanticInterpretationError):
            asyncio.run(self.make_interpreter({
                "goal": "launch_application",
                "operation": "open",
                "target": "calculator",
                "parameters": {},
                "candidate_capabilities": ["open_application"],
            }).interpret("open calculator"))

    def test_unknown_target_is_rejected_by_catalog(self):
        result = asyncio.run(self.make_interpreter({
            "goal": "launch_application",
            "operation": "open",
            "target": "unknown-app",
            "parameters": {},
        }).interpret("open unknown-app"))
        self.assertFalse(result.is_valid)
        self.assertEqual(result.candidate_capabilities, [])
        self.assertIn("unresolved_capability", result.ambiguity)

    def test_shell_content_is_rejected(self):
        with self.assertRaises(SemanticInterpretationError):
            asyncio.run(self.make_interpreter({
                "goal": "launch_application",
                "operation": "open",
                "target": "cmd.exe",
                "parameters": {"command": "start calc.exe"},
            }).interpret("open calculator"))

    def test_provider_timeout_fails_with_bounded_semantic_error(self):
        interpreter = SemanticInterpreter(SlowProvider(), self.make_catalog(), timeout_seconds=0.01)
        with self.assertRaises(SemanticInterpretationError):
            asyncio.run(interpreter.interpret("open calculator"))

    def test_cognitive_core_maps_valid_semantics_to_existing_action_graph(self):
        catalog = self.make_catalog()
        request = SemanticRequest(
            raw_text="bring up the calculator",
            probable_goal="launch_application",
            operation="open",
            entities={"target": "calculator"},
            candidate_capabilities=["open_application"],
            confidence=0.9,
        )
        core = CognitiveCore(
            context_builder_instance=StubContextBuilder(),
            semantic_interpreter_instance=FakeSemanticInterpreter(request, catalog),
        )
        decision = core.cognize("bring up the calculator", user_id="u", session_id="s")
        node = decision.action_graph.nodes[0]
        self.assertEqual(node.engine, "ToolManager")
        self.assertEqual(node.action, "open_app")
        self.assertEqual(node.arguments["app_name"], "calculator")

    def test_cognitive_core_falls_back_to_legacy_classifier(self):
        catalog = self.make_catalog()
        core = CognitiveCore(
            context_builder_instance=StubContextBuilder(),
            classifier=FallbackClassifier(),
            semantic_interpreter_instance=FailingSemanticInterpreter(catalog),
        )
        decision = core.cognize("hello", user_id="u", session_id="s")
        self.assertIsNone(decision.semantic_request)
        self.assertEqual(decision.action_graph.nodes[0].intent, IntentType.CHAT)

    def test_existing_legacy_calculator_planning_remains_available(self):
        plan = ActionPlanner().plan_action("calculate 2 + 2")
        self.assertTrue(plan.is_tool_action)
        self.assertEqual(plan.actions[0].tool_name, "calculator")


if __name__ == "__main__":
    unittest.main()
