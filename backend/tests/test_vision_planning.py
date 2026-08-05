import base64
import unittest
from app.tools.registry import tool_registry
from app.tools.utilities.visual_reader import VisualReaderTool
from app.planning.planner import hierarchical_planner


class TestVisionPlanning(unittest.TestCase):

    def test_visual_reader_tool_registration(self):
        import app.tools
        tool = tool_registry.get_tool("visual_reader")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.manifest.display_name, "Visual Document Reader")

    def test_visual_reader_execution(self):
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        b64_str = base64.b64encode(png_bytes).decode('utf-8')

        tool = tool_registry.get_tool("visual_reader")
        self.assertIsNotNone(tool)

        # Run execute (async in tool, but we test direct async wrapper or mock)
        import asyncio
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(tool.execute({"file_b64": b64_str, "filename": "test_invoice.png"}))
        loop.close()

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["filename"], "test_invoice.png")
        self.assertIn("local", res["provider"])

    def test_planning_engine_vision_step_generation(self):
        tool_action = {"tool_name": "visual_reader", "arguments": {"filename": "receipt.png"}, "reasoning": "User requested visual inspection."}
        plan = hierarchical_planner.create_plan(user_message="Inspect receipt", tool_action=tool_action)

        self.assertEqual(plan.steps[0].tool_name, "visual_reader")
        self.assertIn("visual_reader", plan.steps[0].title.lower())


if __name__ == "__main__":
    unittest.main()
