import asyncio
import platform
import subprocess
import unittest
from unittest.mock import patch
from app.tools.process_verifier import verify_os_process, is_process_running
from app.tools.system.open_application import open_application_tool
from app.router.manager import router_manager
from app.presence.manager import presence_manager


class TestDesktopProcessVerification(unittest.TestCase):

    def test_os_process_verifier_current_python_process(self):
        # Python process should be running in OS process table
        verified, pid, proc_name, err = verify_os_process("python")
        self.assertTrue(verified)
        self.assertIsNotNone(pid)
        self.assertTrue("python" in proc_name.lower())
        self.assertIsNone(err)
        self.assertTrue(is_process_running("python"))

    def test_os_process_verifier_non_existent_process(self):
        verified, pid, proc_name, err = verify_os_process("non_existent_fake_app_12345")
        self.assertFalse(verified)
        self.assertIsNone(pid)
        self.assertIsNotNone(err)

    def test_open_application_tool_returns_required_fields(self):
        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(open_application_tool.execute({"app_name": "notepad"}, dry_run=True))
        loop.close()

        self.assertTrue(res.get("dry_run"))

    def test_execution_pipeline_failed_verification_flow(self):
        async def dummy_failed_launcher():
            return {
                "status": "failed",
                "success": False,
                "verified": False,
                "pid": None,
                "process_name": "notepad.exe",
                "error": "Process 'notepad.exe' was not found in active OS task list."
            }

        loop = asyncio.new_event_loop()
        res = loop.run_until_complete(
            presence_manager.process_directive(
                intent="TOOL_EXECUTION",
                engine_name="ToolManager",
                raw_message="Open Notepad",
                subsystem_executor_fn=dummy_failed_launcher
            )
        )
        loop.close()

        self.assertFalse(res.verified)
        self.assertIn("couldn't verify that it launched", res.natural_response.lower())

    def test_execution_feedback_process_verification_and_retry(self):
        loop = asyncio.new_event_loop()

        # Step 1: User requests Open Notepad
        res1 = loop.run_until_complete(router_manager.route_request("Open Notepad"))
        self.assertEqual(res1["intent"], "TOOL_EXECUTION")

        # Step 2: User complains "I can't see notepad." (Must route to EXECUTION_FEEDBACK, NOT CHAT)
        res2 = loop.run_until_complete(router_manager.route_request("I can't see notepad."))
        loop.close()

        self.assertEqual(res2["intent"], "EXECUTION_FEEDBACK")
        self.assertNotEqual(res2["engine"], "CHAT")
        self.assertTrue("you're right" in res2["response"].lower() or "verified" in res2["response"].lower())


if __name__ == "__main__":
    unittest.main()
