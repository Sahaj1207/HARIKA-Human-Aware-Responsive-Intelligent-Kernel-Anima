"""Website tasks: the safety rules, the step loop, pausing for the user, and the extension's front door."""
import asyncio
import json
import unittest
from typing import Any, Dict, List
from unittest.mock import patch

from app.agents.web_agent import Outcome, WebAgent, WebTask, parse_step
from app.tools.web.browser import policy
from app.tools.web.browser.driver import BrowserDriver, PageError


def page(*elements, url="https://shop.example/", title="Shop", **extra) -> Dict[str, Any]:
    return {"url": url, "title": title, "elements": [dict(e, id=i + 1) for i, e in enumerate(elements)], "text": "Welcome",
            **extra}


SEARCH = {"role": "searchbox", "label": "Search", "value": "", "form": "get"}
PASSWORD = {"role": "password", "label": "Password", "sensitive": True}
CARD = {"role": "text", "label": "Card number", "sensitive": True}
ADD = {"role": "button", "label": "Add to cart"}
ORDER = {"role": "button", "label": "Place your order"}
POST_SUBMIT = {"role": "button", "label": "Save", "submits": True, "form": "post"}
FILTERS = {"role": "button", "label": "Apply filters"}


class PolicyTests(unittest.TestCase):
    def test_sensitive_fields_are_handed_to_the_user(self):
        verdict = policy.check({"action": "type", "id": 1, "text": "hunter2"}, page(PASSWORD))
        self.assertTrue(verdict.hand_over)
        self.assertFalse(verdict.allowed)
        self.assertTrue(policy.check({"action": "type", "id": 1, "text": "4111"}, page(CARD)).hand_over)

    def test_committing_steps_need_a_yes(self):
        self.assertTrue(policy.check({"action": "click", "id": 1}, page(ORDER)).needs_yes)  # its label
        self.assertTrue(policy.check({"action": "click", "id": 1}, page(POST_SUBMIT)).needs_yes)  # posts a form
        self.assertTrue(policy.check({"action": "click", "id": 1, "commits": True}, page(ADD)).needs_yes)  # the model says so
        self.assertTrue(policy.check({"action": "type", "id": 1, "text": "hi", "enter": True},
                                     page({"role": "text", "label": "Comment", "form": "post"})).needs_yes)

    def test_ordinary_steps_just_run(self):
        for step, on in (({"action": "click", "id": 1}, page(ADD)), ({"action": "click", "id": 1}, page(FILTERS)),
                         ({"action": "type", "id": 1, "text": "basmati rice", "enter": True}, page(SEARCH)),
                         ({"action": "open", "url": "https://www.amazon.in/s?k=rice"}, page()),
                         ({"action": "scroll", "direction": "down"}, page())):
            verdict = policy.check(step, on)
            self.assertTrue(verdict.allowed and not verdict.needs_yes and not verdict.hand_over, step)

    def test_invalid_steps_are_refused(self):
        self.assertTrue(policy.check({"action": "open", "url": "file:///C:/Windows"}, page()).problem)
        self.assertTrue(policy.check({"action": "open", "url": "javascript:alert(1)"}, page()).problem)
        self.assertTrue(policy.check({"action": "click", "id": 9}, page(ADD)).problem)
        self.assertTrue(policy.check({"action": "run_shell"}, page()).problem)
        self.assertTrue(policy.check({"action": "click", "id": 1}, page(dict(ADD, disabled=True))).problem)
        self.assertIn("click radio buttons", policy.check({"action": "choose", "id": 1, "text": "Medium"},
                                                          page({"role": "radio", "label": "Medium"})).problem)
        self.assertTrue(policy.check({"action": "choose", "id": 1, "text": "Medium"},
                                     page({"role": "select", "label": "Size", "options": ["Medium"]})).allowed)

    def test_sign_ins_and_captchas_need_the_user(self):
        self.assertIn("sign in", policy.needs_the_user(page(PASSWORD, password_field=True)))
        self.assertIn("human", policy.needs_the_user(page(captcha=True)))
        self.assertEqual(policy.needs_the_user(page(SEARCH)), "")

    def test_steps_in_plain_words(self):
        self.assertEqual(policy.describe_step({"action": "click", "id": 1}, page(ADD)), "click “Add to cart”")
        self.assertEqual(policy.describe_step({"action": "open", "url": "https://www.amazon.in/s?k=x"}, page()),
                         "open www.amazon.in")

    def test_model_replies_are_parsed_strictly(self):
        self.assertEqual(parse_step('Sure: {"action": "click", "id": 3}')["id"], 3)
        self.assertIsNone(parse_step('{"action": "delete_everything"}'))
        self.assertIsNone(parse_step("no json here"))


class FakeBrowser(BrowserDriver):
    name = "test browser"

    def __init__(self, pages: List[Dict[str, Any]]):
        self.pages = pages
        self.done: List[str] = []

    async def start(self):
        pass

    async def snapshot(self):
        return self.pages[0]

    def _next(self):
        if len(self.pages) > 1:
            self.pages.pop(0)

    async def open(self, url):
        if url == "about:blank":  # every new task starts on a blank page
            self.blanked = True
            return
        self.done.append(f"open {url}")
        self._next()

    async def click(self, element_id):
        label = next(e["label"] for e in self.pages[0]["elements"] if e["id"] == element_id)
        self.done.append(f"click {label}")
        self._next()

    async def type(self, element_id, text):
        self.done.append(f"type {text}")

    async def press_enter(self, element_id):
        self.done.append("enter")
        self._next()

    async def choose(self, element_id, option):
        return option

    async def scroll(self, direction):
        self.done.append(f"scroll {direction}")

    async def back(self):
        self.done.append("back")


def scripted(*steps):
    """A model that answers with these steps in turn."""
    replies = list(steps)

    async def ask(task, current_page):
        return replies.pop(0) if replies else {"action": "done", "say": "All done."}
    return ask


class AgentTests(unittest.TestCase):
    def run_agent(self, browser, ask, task=None, approved=False):
        task = task or WebTask(goal="add rice to my cart")
        return asyncio.run(WebAgent(browser, ask=ask).run(task, approved=approved)), task

    def test_a_task_runs_step_by_step_until_done(self):
        browser = FakeBrowser([page(), page(SEARCH), page(ADD, title="Results")])
        outcome, task = self.run_agent(browser, scripted(
            {"action": "open", "url": "https://shop.example/"},
            {"action": "type", "id": 1, "text": "basmati rice", "enter": True},
            {"action": "click", "id": 1},
            {"action": "done", "say": "Added basmati rice (₹120) to your cart."}))
        self.assertEqual(browser.done, ["open https://shop.example/", "type basmati rice", "enter", "click Add to cart"])
        self.assertEqual((outcome.kind, outcome.text), ("done", "Added basmati rice (₹120) to your cart."))
        self.assertIn("click “Add to cart”", task.history)

    def test_a_final_step_waits_for_yes_then_runs_on_the_same_button(self):
        browser = FakeBrowser([page(ORDER, title="Checkout"), page(title="Thank you")])
        outcome, task = self.run_agent(browser, scripted({"action": "click", "id": 1}))
        self.assertEqual(outcome.kind, "needs_yes")
        self.assertIn("click “Place your order”", outcome.text)
        self.assertEqual(browser.done, [])  # nothing happened yet
        # The page re-renders with a banner first: the button's number changed, its label didn't.
        browser.pages[0] = page({"role": "button", "label": "Close banner"}, ORDER, title="Checkout")
        outcome, _ = self.run_agent(browser, scripted({"action": "done", "say": "Ordered."}), task=task, approved=True)
        self.assertEqual(browser.done, ["click Place your order"])
        self.assertEqual(outcome.kind, "done")

    def test_an_early_end_still_says_what_was_done(self):
        browser = FakeBrowser([page(ORDER), page(title="Order placed", url="https://shop.example/thanks")])
        _, task = self.run_agent(browser, scripted({"action": "click", "id": 1}))
        outcome, task = self.run_agent(browser, scripted(*[{"action": "click", "id": 7}] * 3), task=task, approved=True)
        self.assertEqual(outcome.kind, "failed")
        self.assertTrue(outcome.text.startswith("I did click “Place your order”. Then I got stuck"))
        self.assertIn("(now on a new page: Order placed)", task.history)

    def test_an_approved_button_that_vanished_is_not_clicked(self):
        browser = FakeBrowser([page(ORDER)])
        _, task = self.run_agent(browser, scripted({"action": "click", "id": 1}))
        browser.pages[0] = page(ADD)
        self.run_agent(browser, scripted({"action": "done", "say": "ok"}), task=task, approved=True)
        self.assertNotIn("click Add to cart", browser.done)
        self.assertIn("the page changed", task.history[-1])

    def test_sign_in_pages_are_handed_over(self):
        outcome, _ = self.run_agent(FakeBrowser([page(PASSWORD, password_field=True)]), scripted())
        self.assertEqual(outcome.kind, "hand_over")
        self.assertIn("sign in yourself", outcome.text)

    def test_the_model_can_ask_the_user(self):
        outcome, _ = self.run_agent(FakeBrowser([page(ADD)]), scripted({"action": "ask_user", "say": "1 kg or 5 kg?",
                                                                        "asking_for": "choice"}))
        self.assertEqual((outcome.kind, outcome.text), ("ask_user", "1 kg or 5 kg?"))

    def test_a_yes_to_a_plan_covers_the_button_it_named_once(self):
        browser = FakeBrowser([page(SEARCH, ORDER), page(title="Thanks")])
        outcome, task = self.run_agent(browser, scripted(
            {"action": "ask_user", "say": "I'll fill it in and place the order. Go ahead?", "asking_for": "permission"}))
        self.assertEqual(outcome.kind, "ask_user")
        outcome, task = self.run_agent(browser, scripted(
            {"action": "type", "id": 1, "text": "rice"}, {"action": "click", "id": 2, "commits": True},
            {"action": "done", "say": "Ordered."}), task=task, approved=True)
        self.assertEqual(browser.done, ["type rice", "click Place your order"])  # no second question
        self.assertEqual((outcome.kind, task.approval), ("done", ""))

    def test_a_yes_to_a_plan_does_not_cover_a_different_button(self):
        pay = {"role": "button", "label": "Pay now"}
        browser = FakeBrowser([page(pay)])
        _, task = self.run_agent(browser, scripted(
            {"action": "ask_user", "say": "Shall I place the order?", "asking_for": "permission"}))
        outcome, _ = self.run_agent(browser, scripted({"action": "click", "id": 1, "commits": True}), task=task,
                                    approved=True)
        self.assertEqual(outcome.kind, "needs_yes")  # asked again, about "Pay now"
        self.assertEqual(browser.done, [])

    def test_a_yes_to_the_models_own_question_is_passed_on(self):
        browser = FakeBrowser([page(ADD)])
        outcome, task = self.run_agent(browser, scripted({"action": "ask_user", "say": "Use the saved address?",
                                                          "asking_for": "choice"}))
        seen = {}

        async def ask(current_task, current):
            seen["notes"] = list(current_task.notes)
            return {"action": "done", "say": "ok"}

        self.run_agent(browser, ask, task=task, approved=True)
        self.assertEqual(seen["notes"], ["You asked “Use the saved address?” and the user said yes."])

    def test_stop_and_limits(self):
        task = WebTask(goal="x", stop_requested=True)
        self.assertEqual(self.run_agent(FakeBrowser([page()]), scripted(), task=task)[0].kind, "stopped")
        task = WebTask(goal="x", steps_taken=99)
        self.assertEqual(self.run_agent(FakeBrowser([page()]), scripted(), task=task)[0].kind, "limit")

    def test_repeated_bad_steps_end_the_task(self):
        outcome, _ = self.run_agent(FakeBrowser([page(ADD)]), scripted(*[{"action": "click", "id": 42}] * 3))
        self.assertEqual(outcome.kind, "failed")

    def test_an_unreadable_page_is_retried_not_fatal(self):
        class Blank(FakeBrowser):
            reads = 0

            async def snapshot(self):
                Blank.reads += 1
                if Blank.reads == 1:
                    raise PageError("Cannot access contents of this page")
                return self.pages[0]

        outcome, task = self.run_agent(Blank([page(ADD)]), scripted({"action": "done", "say": "ok"}))
        self.assertEqual(outcome.kind, "done")
        self.assertIn("couldn't read the page", task.history[0])

    def test_page_errors_are_noted_not_fatal(self):
        class Flaky(FakeBrowser):
            async def click(self, element_id):
                raise PageError("That element is no longer on the page")

        browser = Flaky([page(ADD)])
        outcome, task = self.run_agent(browser, scripted({"action": "click", "id": 1}, {"action": "done", "say": "ok"}))
        self.assertEqual(outcome.kind, "done")
        self.assertIn("no longer on the page", task.history[0])

    def test_a_step_that_changed_nothing_is_noted_and_waiting_is_limited(self):
        browser = FakeBrowser([page(ADD)])  # clicking doesn't change this page
        seen = {}

        async def ask(task, current):
            seen.setdefault("histories", []).append(list(task.history))
            return [{"action": "click", "id": 1}, {"action": "wait"}, {"action": "wait"}, {"action": "wait"},
                    {"action": "done", "say": "ok"}][len(seen["histories"]) - 1]

        outcome, task = self.run_agent(browser, ask)
        self.assertEqual(seen["histories"][1], ["click “Add to cart”", "(nothing on the page changed after that)"])
        self.assertIn("(waited enough: the page isn't changing on its own)", task.history)
        self.assertEqual(outcome.kind, "done")

    def test_the_page_reaches_the_model_as_quoted_content(self):
        text = WebAgent.page_text(page(SEARCH, PASSWORD, POST_SUBMIT))
        self.assertIn('[1] searchbox "Search"', text)
        self.assertIn("SENSITIVE: the user types this", text)
        self.assertIn("in a form that sends data", text)


class ToolTests(unittest.TestCase):
    def setUp(self):
        from app.tools.web.web_task_tool import WebTaskTool
        self.tool = WebTaskTool()

    def run_tool(self, browser, ask, **args):
        real_init = WebAgent.__init__

        def init(agent, driver, ask_=None, progress=None):
            real_init(agent, driver, ask=ask, progress=progress)

        with patch.object(type(self.tool), "driver", staticmethod(lambda: browser)), \
                patch.object(WebAgent, "__init__", init):
            return asyncio.run(self.tool.execute(args))

    def test_pausing_asks_through_the_router_and_continuing_needs_the_yes(self):
        browser = FakeBrowser([page(ORDER), page(title="Thanks")])
        paused = self.run_tool(browser, scripted({"action": "click", "id": 1}), operation="web", target="order rice")
        confirmation = paused["confirmation"]
        self.assertEqual((confirmation["capability"], confirmation["operation"]), ("web_task_continue", "continue_web"))
        self.assertEqual(confirmation["revise"]["operation"], "guide_web")
        self.assertGreaterEqual(confirmation["ttl"], 600)
        from app.tools.schemas import PermissionLevel
        self.assertEqual(self.tool.permission_for({"operation": "continue_web"}), PermissionLevel.HIGH)
        done = self.run_tool(browser, scripted({"action": "done", "say": "Ordered."}), operation="continue_web")
        self.assertEqual(browser.done, ["click Place your order"])
        self.assertTrue(done["summary"].startswith("Ordered."))
        self.assertIsNone(self.tool.task)

    def test_guidance_replaces_the_waiting_step(self):
        browser = FakeBrowser([page(ORDER, ADD)])
        self.run_tool(browser, scripted({"action": "click", "id": 1}), operation="web", target="buy rice")
        seen = {}

        async def ask(task, current):
            seen["notes"] = list(task.notes)
            return {"action": "done", "say": "Okay, only added it to the cart."}

        self.run_tool(browser, ask, operation="guide_web", instruction="just add it to the cart")
        self.assertEqual(seen["notes"], ["just add it to the cart"])
        self.assertEqual(browser.done, [])

    def test_long_tracking_links_are_shortened(self):
        from app.tools.web.web_task_tool import short_link
        long = "https://www.flipkart.com/logitech-b175/p/itme77?pid=ACC&lid=LST" + "&x=1" * 30
        self.assertEqual(short_link(long), "https://www.flipkart.com/logitech-b175/p/itme77")
        self.assertEqual(short_link("https://www.amazon.in/s?k=rice"), "https://www.amazon.in/s?k=rice")

    def test_nothing_to_continue(self):
        result = self.run_tool(FakeBrowser([page()]), scripted(), operation="continue_web")
        self.assertFalse(result["success"])
        self.assertIn("no website task waiting", result["error"])


class FakeSocket:
    def __init__(self, origin, incoming):
        self.headers = {"origin": origin} if origin else {}
        self.incoming = list(incoming)
        self.sent: List[dict] = []
        self.closed = None
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        from fastapi import WebSocketDisconnect
        if not self.incoming:
            raise WebSocketDisconnect()
        item = self.incoming.pop(0)
        if callable(item):
            item = await item(self)
        return json.dumps(item)

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def close(self, code=1000):
        self.closed = code


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        from app.tools.web.browser import extension_bridge as module
        self.module = module
        self.bridge = module.ExtensionBridge()
        self.code = patch.object(module, "pairing_code", return_value="ABCDE-FGHJK-LMNPQ-RSTUV")
        self.code.start()
        self.events = patch("app.core.live_events.live_events.publish")
        self.events.start()

    def tearDown(self):
        self.events.stop()
        self.code.stop()

    def test_web_pages_cannot_connect(self):
        socket = FakeSocket("https://evil.example", [{"code": "ABCDE-FGHJK-LMNPQ-RSTUV"}])
        asyncio.run(self.bridge.serve(socket))
        self.assertEqual((socket.accepted, socket.closed), (False, 4403))
        socket = FakeSocket(None, [])
        asyncio.run(self.bridge.serve(socket))
        self.assertEqual(socket.closed, 4403)

    def test_a_wrong_code_is_rejected(self):
        socket = FakeSocket("chrome-extension://abc", [{"code": "WRONG"}])
        asyncio.run(self.bridge.serve(socket))
        self.assertEqual(socket.sent[0]["type"], "rejected")
        self.assertEqual(socket.closed, 4401)
        self.assertFalse(self.bridge.connected())

    def test_the_paired_extension_does_page_actions(self):
        async def scenario():
            async def reply(socket):
                # While connected, HARIKA asks for a snapshot; the extension answers it.
                await asyncio.sleep(0)
                request = await asyncio.wait_for(asked, 2)
                return {"id": request["id"], "ok": True, "result": {"url": "https://x.example", "elements": []}}

            asked = asyncio.get_running_loop().create_future()
            socket = FakeSocket("chrome-extension://abc", [{"code": "ABCDE-FGHJK-LMNPQ-RSTUV", "browser": "Microsoft Edge"},
                                                           reply])
            original_send = socket.send_text

            async def send_text(text):
                await original_send(text)
                message = json.loads(text)
                if "cmd" in message and not asked.done():
                    asked.set_result(message)
            socket.send_text = send_text
            serving = asyncio.create_task(self.bridge.serve(socket))
            for _ in range(50):
                if self.bridge.connected():
                    break
                await asyncio.sleep(0.01)
            self.assertEqual(self.bridge.browser, "Microsoft Edge")
            snapshot = await self.bridge.snapshot()
            await serving
            return socket, snapshot

        socket, snapshot = asyncio.run(scenario())
        self.assertEqual(socket.sent[0]["type"], "welcome")
        self.assertEqual(socket.sent[1]["cmd"], "page")
        self.assertEqual(socket.sent[1]["args"], {"name": "snapshot", "params": []})
        self.assertEqual(snapshot["url"], "https://x.example")
        self.assertFalse(self.bridge.connected())  # the socket ended after the reply

    def test_the_extension_folder_carries_the_same_page_script(self):
        import tempfile
        from pathlib import Path
        from app.api.v1.endpoints import browser as endpoint
        target = Path(tempfile.mkdtemp(prefix="harika-ext-")) / "browser-extension"
        with patch.object(endpoint, "data_path", lambda *parts: target):
            folder = endpoint.prepare_extension_folder()
        page_js = Path(endpoint.__file__).resolve().parents[3] / "tools" / "web" / "browser" / "page.js"
        self.assertEqual((folder / "page.js").read_text(encoding="utf-8"), page_js.read_text(encoding="utf-8"))
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("cookies", manifest["permissions"])
        self.assertNotIn("history", manifest["permissions"])


class RouterTests(unittest.TestCase):
    def test_a_paused_task_question_stays_open_as_long_as_the_tool_asks(self):
        from app.router.manager import router_manager
        from app.router.schemas import IntentType
        res = {"result": {"confirmation": {"capability": "web_task_continue", "operation": "continue_web",
                                           "target": "this task", "question": "Signed in?", "ttl": 900}}}
        router_manager._hold_tool_follow_up(res, None, "msg", "u-web", "s-web", IntentType.TOOL_EXECUTION, 1.0, None)
        pending = router_manager._pending.pop(("u-web", "s-web"))
        self.assertEqual(pending.ttl, 900)


if __name__ == "__main__":
    unittest.main()
