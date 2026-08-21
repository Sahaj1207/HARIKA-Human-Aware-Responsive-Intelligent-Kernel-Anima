import unittest

from app.cognition.core import CognitiveCore
from app.cognition.schemas import CognitiveDecision, CognitiveGoal, CognitiveMode
from app.router.action_graph import ActionGraph, ActionNode
from app.router.manager import RouterManager
from app.router.schemas import IntentType, RequestContext
from app.presence.verification import VerificationEngine
from app.tools.capability_resolver import CapabilityResolver
from app.tools.planner import ActionPlanner
from app.tools.schemas import ToolManifest, ToolHealth, PermissionLevel
from app.tools.base_tool import BaseTool
from app.tools.registry import ToolRegistry
from app.memory.manager import MemoryManager
from app.memory.storage import MemoryStorage
from app.memory.models import MemoryItem, MemoryCategory
from app.presence.communication.memory import format_memory_response
import tempfile


class StubContextBuilder:
    def build_context(self, message, user_id="default", session_id="default", conversation_history=None):
        return RequestContext(
            message=message,
            user_id=user_id,
            session_id=session_id,
            conversation_history=conversation_history or [],
        )


class StubClassifier:
    def __init__(self, intent, action="process_chat", engine="CognitionManager", confidence=0.95):
        self.intent = intent
        self.action = action
        self.engine = engine
        self.confidence = confidence

    def classify_request(self, context):
        graph = ActionGraph()
        graph.add_node(
            ActionNode(
                intent=self.intent,
                engine=self.engine,
                action=self.action,
                arguments={"message": context.message},
            )
        )
        return graph, self.confidence


class AliasTool(BaseTool):
    manifest = ToolManifest(
        name="open_application",
        display_name="Application Launcher",
        description="Test application capability",
        permissions=PermissionLevel.LOW,
        capabilities=["open_application", "close_application"],
        target_aliases={"calculator": ["calculator", "calc", "cal"]},
    )

    def health_check(self):
        return ToolHealth()

    async def execute(self, args, dry_run=False):
        return {"success": True, "verified": True, "args": args}


class CognitiveCoreFoundationTests(unittest.TestCase):
    def test_capability_registry_resolves_partial_target_without_classifier_phrase(self):
        registry = ToolRegistry()
        registry.register_tool(AliasTool())
        resolver = CapabilityResolver(registry)

        resolved = resolver.resolve("open_application", "cal")

        self.assertEqual(resolved.capability, "open_application")
        self.assertEqual(resolved.target, "calculator")
        self.assertGreaterEqual(resolved.confidence, 0.8)

    def test_action_planner_consumes_normalized_capability_request(self):
        planner = ActionPlanner()

        plan = planner.plan_capability("open_application", "launch", "calculator")

        self.assertTrue(plan.is_tool_action)
        self.assertEqual(plan.actions[0].tool_name, "open_application")
        self.assertEqual(plan.actions[0].arguments["app_name"], "calculator")

    def test_boredom_goal_drives_answer_instead_of_clarification(self):
        core = CognitiveCore(StubContextBuilder(), StubClassifier(IntentType.UNKNOWN_INTENT, confidence=0.75))

        decision = core.cognize("I'm bored", user_id="u", session_id="bored")

        self.assertEqual(decision.mode, "ANSWER")
        self.assertEqual(decision.goal.probable_goal, "conversation_or_entertainment")
        self.assertFalse(decision.clarification_needed)

    def test_memory_retrieval_isolated_by_user_and_query(self):
        with tempfile.TemporaryDirectory(prefix="harika-memory-test-") as directory:
            manager = MemoryManager(storage=MemoryStorage(directory))
            manager.storage.save_category(
                MemoryCategory.PREFERENCES,
                [MemoryItem(id="cricket", category=MemoryCategory.PREFERENCES, title="User preference", content="I like cricket")],
                user_id="alice",
            )
            manager.storage.save_category(
                MemoryCategory.PREFERENCES,
                [MemoryItem(id="dosa", category=MemoryCategory.PREFERENCES, title="User preference", content="I like dosa")],
                user_id="bob",
            )

            alice = manager.get_memories(query="cricket", user_id="alice")
            bob = manager.get_memories(query="cricket", user_id="bob")

            self.assertEqual([item.content for item in alice], ["I like cricket"])
            self.assertEqual(bob, [])

    def test_broad_memory_response_preserves_all_scoped_facts(self):
        response = format_memory_response(
            "MEMORY_QUERY",
            [
                MemoryItem(id="cricket", category=MemoryCategory.PREFERENCES, title="User Fact: I like cricket", content="I like cricket"),
                MemoryItem(id="dosa", category=MemoryCategory.PREFERENCES, title="User Fact: favourite food is dosa", content="I like dosa"),
            ],
            "What do you remember about me?",
        )

        self.assertIn("cricket", response)
        self.assertIn("dosa", response)
    def test_chat_becomes_answer_goal(self):
        core = CognitiveCore(StubContextBuilder(), StubClassifier(IntentType.CHAT))

        decision = core.cognize("Hey Harika", user_id="u", session_id="s")

        self.assertEqual(decision.mode, "ANSWER")
        self.assertEqual(decision.goal.probable_goal, "conversation")
        self.assertFalse(decision.clarification_needed)

    def test_tool_request_preserves_normalized_action(self):
        core = CognitiveCore(
            StubContextBuilder(),
            StubClassifier(IntentType.TOOL_EXECUTION, action="open_app", engine="ToolManager"),
        )

        decision = core.cognize("Open calculator", user_id="u", session_id="s")

        self.assertEqual(decision.mode, "ACT")
        self.assertEqual(decision.action_graph.nodes[0].action, "open_app")
        self.assertIn("open_app", decision.goal.required_capabilities)

    def test_unknown_request_becomes_clarification(self):
        core = CognitiveCore(
            StubContextBuilder(),
            StubClassifier(IntentType.UNKNOWN_INTENT, confidence=0.75),
        )

        decision = core.cognize("Play that song", user_id="u", session_id="s")

        self.assertEqual(decision.mode, "ASK")
        self.assertTrue(decision.clarification_needed)
        self.assertTrue(decision.clarification_question)

    def test_explicit_memory_request_becomes_remember(self):
        core = CognitiveCore(StubContextBuilder(), StubClassifier(IntentType.MEMORY_STORE, action="add_memory", engine="MemoryManager"))

        decision = core.cognize("Remember that I prefer tea", user_id="u", session_id="s")

        self.assertEqual(decision.mode, "REMEMBER")
        self.assertEqual(decision.goal.probable_goal, "memory")

    def test_unsupported_website_close_is_reported_before_execution(self):
        core = CognitiveCore(
            StubContextBuilder(),
            StubClassifier(IntentType.TOOL_EXECUTION, action="close_website", engine="ToolManager"),
        )

        decision = core.cognize("Close GitHub", user_id="u", session_id="s")

        self.assertEqual(decision.mode, "REPORT_UNSUPPORTED")
        self.assertEqual(decision.action_graph.nodes[0].action, "close_website")

    def test_verification_result_propagates_failure(self):
        result = VerificationEngine().verify_output(
            "ToolManager",
            {"status": "failed", "success": False, "verified": False},
        )

        self.assertFalse(result.tool_verified)
        self.assertFalse(result.overall_valid)

    def test_contextual_follow_up_reuses_active_goal(self):
        core = CognitiveCore(StubContextBuilder(), StubClassifier(IntentType.CHAT))

        first = core.cognize("I'm bored", user_id="u", session_id="s")
        second = core.cognize("Music", user_id="u", session_id="s")

        self.assertEqual(first.goal.probable_goal, "conversation_or_entertainment")
        self.assertEqual(second.goal.probable_goal, "music")
        self.assertEqual(second.goal.context["active_goal"], "conversation_or_entertainment")

    def test_clarifying_mood_message_establishes_follow_up_context(self):
        core = CognitiveCore(StubContextBuilder(), StubClassifier(IntentType.UNKNOWN_INTENT))

        first = core.cognize("I'm bored", user_id="u", session_id="mood")
        second = core.cognize("Music", user_id="u", session_id="mood")

        self.assertEqual(first.mode, "ANSWER")
        self.assertEqual(first.goal.probable_goal, "conversation_or_entertainment")
        self.assertEqual(second.goal.probable_goal, "music")
        self.assertEqual(second.goal.context["active_goal"], "conversation_or_entertainment")

    def test_multi_step_graph_is_preserved(self):
        class MultiStepClassifier(StubClassifier):
            def classify_request(self, context):
                graph = ActionGraph()
                graph.add_node(ActionNode(intent=IntentType.TOOL_EXECUTION, engine="ToolManager", action="open_app"))
                graph.add_node(ActionNode(intent=IntentType.MEMORY_STORE, engine="MemoryManager", action="add_memory"))
                return graph, 0.94

        core = CognitiveCore(StubContextBuilder(), MultiStepClassifier(IntentType.TOOL_EXECUTION))
        decision = core.cognize("Open calculator and remember it", user_id="u", session_id="s")

        self.assertEqual(len(decision.action_graph.nodes), 2)
        self.assertEqual(decision.mode, "ACT")

    def test_router_consumes_cognitive_decision_once(self):
        graph = ActionGraph()
        graph.add_node(ActionNode(intent=IntentType.CHAT, engine="CognitionManager", action="process_chat"))
        decision = CognitiveDecision(
            request="Hey Harika",
            context=RequestContext(message="Hey Harika"),
            goal=CognitiveGoal(
                probable_goal="conversation",
                desired_outcome="Provide a useful conversational answer.",
                confidence=0.99,
            ),
            mode=CognitiveMode.ANSWER,
            confidence=0.99,
            action_graph=graph,
        )

        class FakeCore:
            def __init__(self):
                self.calls = 0

            def cognize(self, **kwargs):
                self.calls += 1
                return decision

        class FakeResolver:
            async def execute_node(self, node, user_id="default"):
                return {"status": "conversational", "message": node.arguments.get("message", "Hey Harika")}

        class FakeHistory:
            def record_decision(self, decision):
                pass

        core = FakeCore()
        router = RouterManager(
            cognitive_core_instance=core,
            sub_resolver=FakeResolver(),
            history=FakeHistory(),
        )

        result = __import__("asyncio").run(router.route_request("Hey Harika"))

        self.assertEqual(core.calls, 1)
        self.assertEqual(result["intent"], "CHAT")
        self.assertEqual(result["action"], "process_chat")


if __name__ == "__main__":
    unittest.main()
