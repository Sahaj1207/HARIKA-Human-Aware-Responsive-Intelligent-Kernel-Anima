import unittest
from app.router.schemas import IntentType, RequestContext
from app.router.context import ContextBuilder
from app.router.classifier import IntentClassifier
from app.router.priority import EnginePriorityResolver


class TestRouterPhase2(unittest.TestCase):

    def setUp(self):
        self.context_builder = ContextBuilder()
        self.classifier = IntentClassifier()
        self.priority_resolver = EnginePriorityResolver()

    def test_stage1_deterministic_calculator(self):
        ctx = self.context_builder.build_context("Calculate 25*18")
        graph, confidence = self.classifier.classify_request(ctx)
        self.assertGreaterEqual(confidence, 0.85)
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.nodes[0].intent, IntentType.TOOL_EXECUTION)
        self.assertEqual(graph.nodes[0].engine, "ToolManager")

    def test_multi_intent_classification(self):
        ctx = self.context_builder.build_context("Calculate 18*25 and remember the answer")
        graph, confidence = self.classifier.classify_request(ctx)
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(graph.nodes[0].intent, IntentType.TOOL_EXECUTION)
        self.assertEqual(graph.nodes[1].intent, IntentType.MEMORY_STORE)

    def test_context_aware_agent_continue(self):
        ctx = RequestContext(message="Continue", active_agent_id="agent-123")
        graph, confidence = self.classifier.classify_request(ctx)
        self.assertEqual(graph.nodes[0].intent, IntentType.AGENT_CONTINUE)
        self.assertEqual(graph.nodes[0].engine, "AgentManager")

    def test_priority_resolver_ordering(self):
        ctx = self.context_builder.build_context("Calculate 18*25 and remember the answer")
        graph, _ = self.classifier.classify_request(ctx)
        sorted_graph = self.priority_resolver.resolve_priority(graph)
        # MemoryManager (90) > ToolManager (80)
        self.assertEqual(sorted_graph.nodes[0].engine, "MemoryManager")


if __name__ == "__main__":
    unittest.main()
