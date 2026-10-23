"""Confirmation flow and system-control behaviour, with all OS effects faked."""
import asyncio
import unittest

from app.cognition.core import CognitiveCore
from app.cognition.schemas import CognitiveDecision, CognitiveGoal, CognitiveMode
from app.router.action_graph import ActionGraph, ActionNode
from app.router.manager import RouterManager
from app.router.schemas import IntentType, RequestContext
from app.tools.base_tool import BaseTool
from app.tools.executor import ToolExecutor
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest, ToolStatusCode
from app.tools.system.system_control import system_control_tool


class RiskyTool(BaseTool):
    manifest = ToolManifest(name="risky", display_name="Risky", description="High-risk test tool.", permissions=PermissionLevel.HIGH)

    def __init__(self):
        self.runs = 0

    def health_check(self):
        return ToolHealth()

    async def execute(self, args, dry_run=False):
        self.runs += 1
        return {"success": True, "verified": True}


def shutdown_graph():
    graph = ActionGraph()
    graph.add_node(ActionNode(
        intent=IntentType.TOOL_EXECUTION, engine="ToolManager", action="power_control",
        arguments={"target": "computer", "operation": "shutdown", "query": "shut down"},
    ))
    return graph


class FakeCore:
    def __init__(self, graph, verdict="confirm"):
        self.graph, self.verdict, self.cognized = graph, verdict, []

    async def cognize_async(self, message, **kwargs):
        self.cognized.append(message)
        graph = self.graph if message.startswith("shut") else ActionGraph(nodes=[
            ActionNode(intent=IntentType.CHAT, engine="CognitionManager", action="process_chat", arguments={"message": message})
        ])
        return CognitiveDecision(
            request=message, context=RequestContext(message=message),
            goal=CognitiveGoal(probable_goal="g", desired_outcome="d", confidence=0.95),
            mode=CognitiveMode.ACT, confidence=0.95, action_graph=graph,
        )

    async def interpret_confirmation(self, reply, question):
        return self.verdict


class RecordingResolver:
    def __init__(self):
        self.executed = []

    async def execute_node(self, node, user_id="default"):
        self.executed.append((node.action, node.confirmed))
        return {"status": "success", "success": True, "verified": True, "tool": node.action, "result": {"summary": "done"}}


class NoHistory:
    def record_decision(self, decision):
        pass


def make_router(verdict):
    resolver = RecordingResolver()
    core = FakeCore(shutdown_graph(), verdict)
    return RouterManager(cognitive_core_instance=core, sub_resolver=resolver, history=NoHistory()), core, resolver


class ConfirmationFlowTests(unittest.TestCase):
    def test_risky_action_asks_first_and_runs_after_yes(self):
        router, _, resolver = make_router("confirm")
        first = asyncio.run(router.route_request("shut down the computer"))
        self.assertTrue(first.get("confirmation_needed"))
        self.assertIn("shut down the computer in 60 seconds", first["response"])
        self.assertEqual(resolver.executed, [])

        asyncio.run(router.route_request("go ahead"))
        self.assertEqual(resolver.executed, [("power_control", True)])

    def test_decline_does_not_execute(self):
        router, _, resolver = make_router("decline")
        asyncio.run(router.route_request("shut down the computer"))
        reply = asyncio.run(router.route_request("actually no"))
        self.assertEqual(resolver.executed, [])
        self.assertIn("won't", reply["response"])

    def test_unrelated_reply_drops_pending_action_and_is_handled_normally(self):
        router, core, resolver = make_router("other")
        asyncio.run(router.route_request("shut down the computer"))
        asyncio.run(router.route_request("what's the weather like"))
        self.assertEqual(core.cognized[-1], "what's the weather like")
        self.assertNotIn(("power_control", True), resolver.executed)
        # The dropped action can't be revived by a later "yes".
        asyncio.run(router.route_request("yes"))
        self.assertNotIn(("power_control", True), resolver.executed)

    def expire(self, router):
        for pending in router._pending.values():
            pending.created_at -= pending.ttl + 5

    def test_late_yes_asks_again_instead_of_acting(self):
        router, core, resolver = make_router("confirm")
        asyncio.run(router.route_request("shut down the computer"))
        self.expire(router)
        late = asyncio.run(router.route_request("yes"))
        self.assertEqual(resolver.executed, [])  # never acted on a stale approval
        self.assertIn("haven't done it yet", late["response"])
        self.assertIn("shut down the computer in 60 seconds", late["response"])
        self.assertNotIn("yes", core.cognized)  # not passed on as small talk
        asyncio.run(router.route_request("yes"))  # the fresh yes
        self.assertEqual(resolver.executed, [("power_control", True)])

    def test_late_no_lets_it_go(self):
        router, _, resolver = make_router("decline")
        asyncio.run(router.route_request("shut down the computer"))
        self.expire(router)
        self.assertIn("let that go", asyncio.run(router.route_request("no"))["response"])
        self.assertEqual(resolver.executed, [])
        self.assertEqual(router._pending, {})

    def test_new_request_after_an_expired_question_is_handled_normally(self):
        router, core, resolver = make_router("other")
        asyncio.run(router.route_request("shut down the computer"))
        self.expire(router)
        asyncio.run(router.route_request("what's the weather like"))
        self.assertEqual(core.cognized[-1], "what's the weather like")
        self.assertEqual(router._expired, {})  # asked about once, then forgotten

    def test_bare_yes_no_need_no_model(self):
        core = CognitiveCore()
        self.assertEqual(asyncio.run(core.interpret_confirmation("Yes!", "q")), "confirm")
        self.assertEqual(asyncio.run(core.interpret_confirmation("no", "q")), "decline")
        # Without an interpreter, anything ambiguous is never treated as approval.
        self.assertEqual(asyncio.run(core.interpret_confirmation("sure why not", "q")), "other")


class ExecutorEnforcementTests(unittest.TestCase):
    def test_high_risk_tool_refused_without_router_confirmation(self):
        tool, executor = RiskyTool(), ToolExecutor()
        executor._save_history = lambda: None
        refused = asyncio.run(executor.execute_tool(tool, {"confirmed": True}))
        self.assertEqual(refused.status_code, ToolStatusCode.CONFIRMATION_REQUIRED)
        self.assertEqual(tool.runs, 0)

        allowed = asyncio.run(executor.execute_tool(tool, {}, confirmed=True))
        self.assertTrue(allowed.success)
        self.assertEqual(tool.runs, 1)

    def test_operation_risk_only_raises_tool_level(self):
        self.assertEqual(system_control_tool.permission_for({"operation": "shutdown"}), PermissionLevel.HIGH)
        self.assertEqual(system_control_tool.permission_for({"operation": "lock"}), PermissionLevel.LOW)


class SystemControlTests(unittest.TestCase):
    def test_levels_parse_numbers_percentages_and_fractions(self):
        parse = system_control_tool._percent
        self.assertEqual((parse(40), parse("40%"), parse("0.4"), parse("a bit"), parse(150)), (40, 40, 40, None, None))

    def test_operations_without_targets_use_defaults(self):
        self.assertEqual(system_control_tool.match_target("", "mute"), ("volume", 0.8))
        self.assertEqual(system_control_tool.match_target("my laptop", "lock"), ("computer", 0.8))
        self.assertEqual(system_control_tool.match_target("speakers", "set")[0], "volume")
        self.assertEqual(system_control_tool.match_target("toaster", "set"), (None, 0.0))

    def test_set_requires_a_level_and_a_known_target(self):
        self.assertFalse(system_control_tool.validate({"operation": "set", "target": "volume"})[0])
        self.assertFalse(system_control_tool.validate({"operation": "set", "target": "toaster", "level": 3})[0])
        self.assertTrue(system_control_tool.validate({"operation": "set", "target": "brightness", "level": 50})[0])


if __name__ == "__main__":
    unittest.main()
