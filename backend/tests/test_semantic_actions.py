"""Focused tests for semantic action plans, capability resolution and safe execution.

Everything here uses fake providers/registries or dry runs: no app, browser or
network side effects.
"""
import asyncio
import json
import unittest
from unittest.mock import patch

from app.cognition.core import CognitiveCore
from app.cognition.semantic.catalog import CapabilityCatalog
from app.cognition.semantic.interpreter import SemanticInterpreter
from app.router.action_graph import ActionGraph, ActionNode
from app.router.manager import RouterManager
from app.router.schemas import IntentType, RequestContext
from app.tools.base_tool import BaseTool
from app.tools.capability_resolver import CapabilityResolver
from app.tools.registry import ToolRegistry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest


class _Tool(BaseTool):
    def health_check(self):
        return ToolHealth()

    async def execute(self, args, dry_run=False):
        return {"success": True, "verified": True, "args": args}


class AppTool(_Tool):
    manifest = ToolManifest(
        name="open_application",
        display_name="open_application",
        description="Launches applications.",
        permissions=PermissionLevel.LOW,
        capabilities=["open_application", "close_application"],
        operations={"open": "open_application", "close": "close_application"},
        target_aliases={"calculator": ["calculator", "calc"], "notepad": ["notepad"], "chrome": ["chrome"]},
    )


class SiteTool(_Tool):
    manifest = ToolManifest(
        name="open_website",
        display_name="open_website",
        description="Opens websites.",
        permissions=PermissionLevel.LOW,
        capabilities=["open_website", "close_website"],
        operations={"open": "open_website", "close": "close_website"},
        target_aliases={"youtube": ["youtube"], "twitter": ["twitter", "x"]},
    )


class MediaTool(_Tool):
    manifest = ToolManifest(
        name="media_playback",
        display_name="media_playback",
        description="Plays media.",
        permissions=PermissionLevel.LOW,
        capabilities=["play_media"],
        operations={"play": "play_media"},
        free_text_operations=["play"],
    )


class SearchTool(_Tool):
    manifest = ToolManifest(
        name="web_search",
        display_name="web_search",
        description="Searches the web.",
        permissions=PermissionLevel.LOW,
        capabilities=["web_search", "open_search_result"],
        operations={"search": "web_search", "open": "open_search_result"},
        free_text_operations=["search"],
        target_aliases={"1": ["first result"]},
    )


class NoRouterCapabilities:
    def get_capabilities(self):
        return []


class StubContextBuilder:
    def build_context(self, message, user_id="default", session_id="default", conversation_history=None):
        return RequestContext(message=message, user_id=user_id, session_id=session_id)


class UnknownClassifier:
    def classify_request(self, context):
        graph = ActionGraph()
        graph.add_node(ActionNode(intent=IntentType.UNKNOWN_INTENT, engine="CognitionManager", action="unknown_intent"))
        return graph, 0.5


class RecordingProvider:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    async def generate_response(self, messages, system_prompt):
        self.prompts.append(system_prompt)
        return {"response": self.payload if isinstance(self.payload, str) else json.dumps(self.payload)}


def make_registry():
    registry = ToolRegistry()
    for tool in (AppTool(), SiteTool(), MediaTool(), SearchTool()):
        registry.register_tool(tool)
    return registry


def make_interpreter(payload):
    catalog = CapabilityCatalog.from_sources(make_registry(), NoRouterCapabilities())
    return SemanticInterpreter(RecordingProvider(payload), catalog)


def make_core(payload):
    interpreter = make_interpreter(payload)
    core = CognitiveCore(StubContextBuilder(), UnknownClassifier(), semantic_interpreter_instance=interpreter)
    return core, interpreter


class CapabilityResolutionTests(unittest.TestCase):
    def setUp(self):
        self.resolver = CapabilityResolver(make_registry())

    def test_typo_resolves_to_registered_target(self):
        resolved = self.resolver.resolve_operation("open", "calci")
        self.assertTrue(resolved.supported)
        self.assertEqual(resolved.target, "calculator")

    def test_short_alias_does_not_capture_longer_words(self):
        self.assertFalse(self.resolver.resolve_operation("open", "xbox").supported)

    def test_free_text_operation_accepts_query(self):
        resolved = self.resolver.resolve_operation("play", "lofi beats")
        self.assertEqual((resolved.capability, resolved.target), ("play_media", "lofi beats"))

    def test_registered_target_beats_free_text_and_ordinals(self):
        self.assertEqual(self.resolver.resolve_operation("open", "first result").capability, "open_search_result")
        self.assertEqual(self.resolver.resolve_operation("open", "youtube").capability, "open_website")

    def test_unknown_operation_is_unsupported(self):
        self.assertFalse(self.resolver.resolve_operation("delete", "calculator").supported)


class SemanticPlanTests(unittest.TestCase):
    def test_ordered_actions_become_dependent_nodes(self):
        core, _ = make_core({"actions": [
            {"operation": "open", "target": "chrome", "parameters": {}},
            {"operation": "search", "target": "F1 news", "parameters": {}},
            {"action": "open", "target": "first result"},
        ]})
        decision = core.cognize("open chrome, search F1 news and open the first result", user_id="u", session_id="s")
        nodes = decision.action_graph.nodes
        self.assertEqual([n.action for n in nodes], ["open_app", "web_search", "open_search_result"])
        self.assertEqual(nodes[1].dependencies, [nodes[0].id])
        self.assertEqual(nodes[2].dependencies, [nodes[1].id])
        self.assertEqual(decision.mode, "ACT")

    def test_empty_action_list_means_answer_not_clarify(self):
        core, _ = make_core({"actions": []})
        decision = core.cognize("what is the capital of France?", user_id="u", session_id="s")
        self.assertEqual(decision.mode, "ANSWER")
        self.assertEqual(decision.action_graph.nodes[0].intent, IntentType.CHAT)
        self.assertFalse(decision.clarification_needed)

    def test_unsupported_step_gets_specific_explanation(self):
        core, _ = make_core({"actions": [{"operation": "open", "target": "blorptastic", "parameters": {}}]})
        decision = core.cognize("open blorptastic", user_id="u", session_id="s")
        self.assertEqual(decision.mode, "ASK")
        self.assertIn("blorptastic", decision.clarification_question)

    def test_fenced_json_is_accepted(self):
        payload = '```json\n{"actions": [{"operation": "play", "target": "lofi", "parameters": {}}]}\n```'
        result = asyncio.run(make_interpreter(payload).interpret("play lofi"))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.candidate_capabilities, ["play_media"])

    def test_unknown_keys_in_action_are_rejected(self):
        from app.cognition.semantic.interpreter import SemanticInterpretationError
        with self.assertRaises(SemanticInterpretationError):
            asyncio.run(make_interpreter({"actions": [{"operation": "open", "target": "calc", "path": "C:/x.exe"}]}).interpret("x"))

    def test_prompt_lists_registered_operations_and_recent_actions(self):
        core, interpreter = make_core({"actions": [{"operation": "close", "target": "calculator", "parameters": {}}]})
        core._session_actions[("u", "s")] = __import__("collections").deque(["open calculator"])
        decision = core.cognize("now close it", user_id="u", session_id="s")
        prompt = interpreter.provider.prompts[-1]
        self.assertIn('"play"', prompt)
        self.assertIn("HARIKA recently did: open calculator", prompt)
        self.assertEqual(decision.action_graph.nodes[0].action, "close_app")


class RouterCompoundExecutionTests(unittest.TestCase):
    def test_failed_step_halts_remaining_steps(self):
        graph = ActionGraph()
        for action in ("open_app", "web_search", "open_search_result"):
            graph.add_node(ActionNode(intent=IntentType.TOOL_EXECUTION, engine="ToolManager", action=action))

        class Core:
            async def cognize_async(self, **kwargs):
                from app.cognition.schemas import CognitiveDecision, CognitiveGoal, CognitiveMode
                return CognitiveDecision(
                    request="x", context=RequestContext(message="x"),
                    goal=CognitiveGoal(probable_goal="g", desired_outcome="d", confidence=0.95),
                    mode=CognitiveMode.ACT, confidence=0.95, action_graph=graph,
                )

        executed = []

        class Resolver:
            async def execute_node(self, node, user_id="default"):
                executed.append(node.action)
                ok = node.action != "web_search"
                return {"status": "success" if ok else "failed", "success": ok, "verified": ok, "tool": node.action, "error": None if ok else "offline"}

        class History:
            def record_decision(self, decision):
                pass

        router = RouterManager(cognitive_core_instance=Core(), sub_resolver=Resolver(), history=History())
        result = asyncio.run(router.route_request("x"))
        self.assertEqual(executed, ["open_app", "web_search"])
        self.assertEqual(graph.nodes[2].status, "skipped")
        self.assertIn("stopped before the remaining 1 step", result["response"])


class SafeExecutionTests(unittest.TestCase):
    def test_unknown_app_is_never_passed_to_a_shell(self):
        from app.tools.system.open_application import open_application_tool
        with patch("app.tools.system.installed_apps.installed_app_index.find", return_value=None), \
             patch("app.tools.system.open_application.subprocess.Popen") as popen:
            result = asyncio.run(open_application_tool.execute({"app_name": "calc & del important.txt"}))
        popen.assert_not_called()
        self.assertFalse(result["success"])

    def test_installed_app_launches_by_os_app_id_without_shell(self):
        from app.tools.system.installed_apps import InstalledApp
        from app.tools.system.open_application import open_application_tool
        app = InstalledApp(name="Spotify", app_id="SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify")
        with patch("app.tools.system.installed_apps.installed_app_index.find", return_value=app), \
             patch("app.tools.system.open_application.platform.system", return_value="Windows"):
            result = asyncio.run(open_application_tool.execute({"app_name": "spotify"}, dry_run=True))
        self.assertEqual(result["app_id"], app.app_id)

    def test_website_tool_accepts_domains(self):
        from app.tools.system.open_website import open_website_tool
        self.assertEqual(open_website_tool.match_target("wikipedia.org", "open"), ("wikipedia.org", 0.9))
        self.assertEqual(open_website_tool.match_target("blorptastic", "open")[0], None)

    def test_open_result_without_search_fails_honestly(self):
        from app.tools import recent_results
        from app.tools.web.web_search import WebSearchTool
        recent_results.remember("test", [])
        result = asyncio.run(WebSearchTool().execute({"operation": "open", "target": "1"}))
        self.assertFalse(result["success"])
        self.assertIn("search", result["error"])

    def test_search_result_redirects_are_unwrapped(self):
        from app.tools.web.web_search import WebSearchTool
        href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.formula1.com%2Fen%2Flatest&rut=abc"
        self.assertEqual(WebSearchTool._real_url(href), "https://www.formula1.com/en/latest")

    def test_media_platform_and_query_are_normalized(self):
        from app.tools.web.media_playback import media_playback_tool
        self.assertEqual(media_playback_tool._query_and_platform({"target": "YouTube", "search": "song"}), ("song", "youtube"))
        self.assertEqual(media_playback_tool._query_and_platform({"target": "lofi", "platform": "Spotify"}), ("lofi", "spotify"))


if __name__ == "__main__":
    unittest.main()
