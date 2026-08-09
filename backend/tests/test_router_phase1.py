import unittest
from app.router.schemas import IntentType, EngineCapability, RequestContext
from app.router.context import ContextBuilder
from app.router.registry import RouterRegistry


class TestRouterPhase1(unittest.TestCase):

    def setUp(self):
        self.context_builder = ContextBuilder()
        self.registry = RouterRegistry()

    def test_request_context_creation(self):
        ctx = self.context_builder.build_context("Calculate 5 + 5", user_id="test_u")
        self.assertEqual(ctx.message, "Calculate 5 + 5")
        self.assertEqual(ctx.user_id, "test_u")
        self.assertIsInstance(ctx.conversation_history, list)

    def test_engine_capability_registration(self):
        cap = EngineCapability(
            engine="ToolManager",
            intents=[IntentType.TOOL_EXECUTION],
            actions=["calculator", "datetime"]
        )
        self.registry.register_engine("ToolManager", object(), cap)

        caps = self.registry.get_capabilities()
        self.assertGreaterEqual(len(caps), 1)
        tool_cap = next(c for c in caps if c.engine == "ToolManager")
        self.assertEqual(tool_cap.engine, "ToolManager")
        self.assertIn(IntentType.TOOL_EXECUTION, tool_cap.intents)



if __name__ == "__main__":
    unittest.main()
