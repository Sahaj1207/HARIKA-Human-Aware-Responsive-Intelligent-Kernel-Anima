import asyncio
import unittest
from app.router.schemas import IntentType, SimulationRequest
from app.router.action_graph import ActionNode
from app.router.resolver import SubsystemResolver
from app.router.events import router_event_bus, RouterEventType


class TestRouterPhase4(unittest.TestCase):

    def setUp(self):
        self.resolver = SubsystemResolver()

    def test_tool_manager_facade_execution(self):
        node = ActionNode(
            intent=IntentType.TOOL_EXECUTION,
            engine="ToolManager",
            action="calculator",
            arguments={"query": "25 * 18"}
        )
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(self.resolver.execute_node(node))
        loop.close()

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["result"]["result"], 450)


    def test_router_event_bus_emissions(self):
        emitted = []
        for et in RouterEventType:
            router_event_bus.subscribe(et, lambda name, p: emitted.append(name))

        router_event_bus.emit(RouterEventType.INTENT_DETECTED, {})
        router_event_bus.emit(RouterEventType.ENGINE_SELECTED, {})
        router_event_bus.emit(RouterEventType.ENGINE_COMPLETED, {})

        self.assertEqual(len(emitted), 3)


if __name__ == "__main__":
    unittest.main()
