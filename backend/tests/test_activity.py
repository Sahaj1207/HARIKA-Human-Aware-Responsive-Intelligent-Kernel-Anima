"""Settings > Activity: what HARIKA did, why, whether it needed a yes, and how it went."""
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.memory import activity
from app.memory.activity import ActivityLog
from app.router.action_graph import ActionGraph, ActionNode
from app.router.schemas import IntentType


def log() -> ActivityLog:
    folder = Path(tempfile.mkdtemp(prefix="harika-activity-"))
    return ActivityLog(folder / "activity", folder / "settings.json")


def node(status="completed", result=None, confirmed=False, operation="open", target="calculator"):
    n = ActionNode(intent=IntentType.TOOL_EXECUTION, engine="ToolManager", action="open_application",
                   arguments={"operation": operation, "target": target}, confirmed=confirmed)
    n.status, n.result = status, result
    return n


class LogTests(unittest.TestCase):
    def test_entries_newest_first_and_the_approval_filter(self):
        history = log()
        history.add("open calculator", when=datetime.now() - timedelta(minutes=5))
        history.add("send reply to Ananya", activity.SAID_YES, activity.APPROVED)
        entries = history.entries()
        self.assertEqual([e["what"] for e in entries], ["Send reply to Ananya", "Open calculator"])
        self.assertEqual([e["what"] for e in history.entries(needed_approval=True)], ["Send reply to Ananya"])
        self.assertEqual(entries[1]["result"], activity.DONE)

    def test_off_clear_and_prune(self):
        history = log()
        history.set_keeping(False)
        history.add("open calculator")
        self.assertEqual(history.entries(), [])
        history.set_keeping(True)
        history.add("open calculator")
        history.add("old thing", when=datetime.now() - timedelta(days=40))
        history.prune()
        self.assertFalse((history.folder / f"{(date.today() - timedelta(days=40)).isoformat()}.jsonl").exists())
        history.clear()
        self.assertEqual(history.entries(), [])

    def test_a_broken_log_never_raises(self):
        folder = Path(tempfile.mkdtemp(prefix="harika-activity-"))
        (folder / "activity").write_text("a file where the folder should be")
        ActivityLog(folder / "activity", folder / "settings.json").add("open calculator")  # no exception


class RouterTests(unittest.TestCase):
    def setUp(self):
        from app.router.manager import router_manager
        self.router = router_manager
        self.history = log()
        self.patch = patch.object(activity, "activity_log", self.history)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def record(self, *nodes, user="u1", labels=None):
        graph = ActionGraph()
        for n in nodes:
            graph.add_node(n)
        self.router._record_activity(graph, user, labels)
        return self.history.entries()

    def test_each_kind_of_outcome(self):
        entries = self.record(
            node(result={"success": True, "verified": True}),
            node(status="failed", result={"success": False, "error": "Calculator isn't installed"}),
            node(status="skipped"),
            node(result={"result": {"success": True, "confirmation": {"question": "Should I send it?"}}}),
            node(result={"result": {"success": True, "verified": False}}),
            node(result={"result": {"success": True, "handed_over": True,
                                    "confirmation": {"question": "The next step pays. Please enter your PIN."}}}),
        )[::-1]
        self.assertEqual([(e["result"], e["approval"]) for e in entries], [
            (activity.DONE, activity.NOT_NEEDED), (activity.FAILED, activity.NOT_NEEDED),
            (activity.NOT_DONE, activity.NOT_NEEDED), (activity.ASKED_YOU, activity.WAITING),
            (activity.UNCONFIRMED, activity.NOT_NEEDED), (activity.HANDED_OVER, activity.HANDED_OVER)])
        self.assertEqual(entries[1]["detail"], "Calculator isn't installed")
        self.assertEqual(entries[3]["detail"], "Should I send it?")

    def test_approved_steps_and_routines_say_why(self):
        approved = self.record(node(result={"success": True}, confirmed=True))[0]
        self.assertEqual((approved["why"], approved["approval"]), (activity.SAID_YES, activity.APPROVED))
        routine = self.record(node(result={"success": True}), user="routines")[0]
        self.assertEqual(routine["why"], activity.ROUTINE)

    def test_the_label_taken_before_the_step_ran_is_used(self):
        n = node(result={"success": True})
        entry = self.record(n, labels={n.id: "click “Place your order”"})[0]
        self.assertEqual(entry["what"], "Click “Place your order”")

    def test_declined_and_expired_questions(self):
        from app.router.manager import _PendingPlan
        graph = ActionGraph()
        graph.add_node(node(operation="shutdown", target="computer"))
        pending = _PendingPlan(graph=graph, context=None, intent=IntentType.TOOL_EXECUTION, confidence=1.0,
                               policy=None, question="Shut down the computer?", created_at=time.time())
        self.router._record_unanswered(pending, activity.DECLINED)
        entry = self.history.entries()[0]
        self.assertEqual((entry["approval"], entry["result"], entry["detail"]),
                         (activity.DECLINED, activity.NOT_DONE, "Shut down the computer?"))
        pending.created_at, pending.ttl = time.time() - 500, 120
        self.router._pending[("u9", "s9")] = pending
        self.assertIsNone(self.router._take_pending("u9", "s9"))
        self.assertEqual(self.history.entries()[0]["approval"], activity.EXPIRED)
        self.router._expired.pop(("u9", "s9"), None)

    def test_recording_problems_never_reach_the_reply(self):
        with patch.object(self.history, "add", side_effect=RuntimeError("disk full")):
            self.record(node(result={"success": True}))  # no exception


class EndpointTests(unittest.TestCase):
    def test_show_switch_off_and_clear(self):
        from app.main import app
        history = log()
        history.add("open calculator")
        local = TestClient(app, client=("127.0.0.1", 50000))
        with patch("app.api.v1.endpoints.activity.activity_log", history):
            shown = local.get("/api/v1/activity").json()
            self.assertEqual((shown["keep"], shown["entries"][0]["what"]), (True, "Open calculator"))
            self.assertFalse(local.put("/api/v1/activity/settings", json={"keep": False}).json()["keep"])
            refused = local.post("/api/v1/activity/clear", headers={"Origin": "https://evil.example"})
            self.assertEqual(refused.status_code, 403)
            self.assertEqual(local.post("/api/v1/activity/clear").json()["entries"], [])


if __name__ == "__main__":
    unittest.main()
