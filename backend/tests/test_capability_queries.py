import asyncio
import unittest
from app.router.manager import router_manager
from app.presence.capability_manager import capability_manager


class TestCapabilityQueries(unittest.TestCase):

    def test_capability_manager_dynamic_generation(self):
        caps = capability_manager.get_all_capabilities()
        self.assertGreater(len(caps), 3)
        summary = capability_manager.format_capability_summary()
        self.assertIn("I can assist you across the following capabilities:", summary)
        self.assertIn("Desktop & Web Tools Engine", summary)


    def test_capability_query_routing_and_responses(self):
        loop = asyncio.new_event_loop()
        test_queries = [
            "What can you do?",
            "Help",
            "Capabilities",
            "Commands",
            "what else can you do"
        ]

        for query in test_queries:
            res = loop.run_until_complete(router_manager.route_request(query))
            self.assertEqual(res["intent"], "CAPABILITY_QUERY", f"Failed intent matching for '{query}'")
            resp = res["response"]
            self.assertIn("capabilities:", resp.lower(), f"Failed response body for '{query}': {resp}")
            self.assertTrue(any(k in resp for k in ["ToolManager", "MemoryManager", "Planning", "Vision", "Voice"]), f"Missing subsystem in response for '{query}'")

        loop.close()


if __name__ == "__main__":
    unittest.main()
