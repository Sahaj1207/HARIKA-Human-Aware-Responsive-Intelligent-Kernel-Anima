"""Website tasks: "find the cheapest flight to Goa on Saturday", "add 1 kg rice to my Amazon cart".

Runs app/agents/web_agent.py in a browser the user can watch: their own Chrome or Edge
when HARIKA's extension is connected, otherwise HARIKA's own browser window. When the
task needs the user (a yes before something final, a sign-in, a choice), it pauses and
asks; their answer comes back here as an ordinary approved step ("continue_web") or as
guidance ("guide_web").
"""
import logging
import time
from typing import Any, Dict, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest

logger = logging.getLogger("harika.tools.web_task")

PAUSE_TTL_SECONDS = 15 * 60  # a paused task waits this long for the user
_THIS_TASK = "this task"


class WebTaskTool(BaseTool):
    manifest = ToolManifest(
        name="web_task",
        display_name="Website tasks",
        description="Shops, orders, books and fills in forms on websites, or checks a price or detail on a site and "
                    "reports back, in a browser window the user can watch (asking before anything final).",
        version="1.0.0",
        author="HARIKA OS Core",
        category="web",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "darwin"],
        capabilities=["web_task", "web_task_continue", "web_task_guide"],
        # Going on with a paused task is never an operation the model can choose: it only follows
        # the user's answer to HARIKA's question.
        operations={"web": "web_task"},
        free_text_operations=["web"],
        operation_permissions={"continue_web": PermissionLevel.HIGH},
        ability="do things on websites for you while you watch: find, compare, fill in, add to cart (asking before anything final)",
        target_description=("the whole task in the user's words, self-contained, naming the site when they did "
                            "(e.g. 'add 1 kg basmati rice to my Amazon cart', 'find flights from Hyderabad to Goa on Saturday "
                            "on Google Flights')"),
    )
    timeout_seconds = 420.0

    def __init__(self):
        super().__init__()
        self.task = None
        self.agent = None
        self.paused_at = 0.0

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Uses your browser through HARIKA's extension, or HARIKA's own window")

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        return (text, 0.7) if text else (None, 0.0)

    def describe_action(self, args: Dict[str, Any]) -> str:
        if args.get("operation") == "continue_web" and self.task and self.task.pending is not None:
            return self.task.pending_label
        return f"do this on the web: {args.get('target') or 'your task'}"

    def stop(self) -> bool:
        if self.task is None or self.agent is None:
            return False
        self.task.stop_requested = True
        return True

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        from app.agents.web_agent import WebTask

        operation = args.get("operation") or "web"
        if operation in ("continue_web", "guide_web"):
            if self.task is None or time.time() - self.paused_at > PAUSE_TTL_SECONDS:
                return self._fail("There's no website task waiting. Tell me what to do and I'll start again")
            if operation == "guide_web":
                said = str(args.get("instruction") or args.get("query") or "").strip()
                if said:
                    asked = f"You asked “{self.task.asked}”; the user answered: " if self.task.asked else ""
                    self.task.notes.append(asked + said)
                self.task.asked = ""
                self.task.pending = None  # their words replace the step that was waiting
            if dry_run:
                return {"dry_run": True, "action": "web_task", "goal": self.task.goal}
            return await self._run(approved=operation == "continue_web")

        goal = str(args.get("target") or args.get("request") or "").strip()
        if not goal:
            return self._fail("What should I do on the web?")
        if dry_run:
            return {"dry_run": True, "action": "web_task", "goal": goal}
        self.task = WebTask(goal=goal)
        return await self._run(approved=False)

    async def _run(self, approved: bool) -> Dict[str, Any]:
        from app.agents.web_agent import WebAgent
        from app.core.live_events import live_events
        from app.tools.web.browser.driver import BrowserUnavailable

        driver = self.driver()
        self.agent = WebAgent(driver, progress=lambda text: live_events.publish("activity", text=text, stoppable=True))
        self.task.stop_requested = False
        try:
            outcome = await self.agent.run(self.task, approved=approved)
        except BrowserUnavailable as exc:
            self.task = None
            return self._fail(str(exc))
        except Exception as exc:
            logger.warning(f"[Web] Task failed: {exc}")
            return self._fail(f"Something went wrong in the browser ({exc}). The window shows where I got to")
        finally:
            self.agent = None
            live_events.publish("activity", text="", stoppable=False)

        where = f"\n\n{outcome.url}" if outcome.url and outcome.kind in ("done", "limit", "failed") else ""
        result: Dict[str, Any] = {"action": "web_task", "success": outcome.kind not in ("failed",),
                                  "verified": outcome.kind == "done", "summary": outcome.text + where,
                                  "error": None if outcome.kind != "failed" else outcome.text, "url": outcome.url,
                                  "browser": driver.name}
        if outcome.kind in ("needs_yes", "hand_over", "ask_user"):
            self.paused_at = time.time()
            # The user's answer: "yes" / "done" runs continue_web (approved); anything else ("pick the
            # cheaper one") goes back to the task as guidance.
            result["confirmation"] = {
                "capability": "web_task_continue", "operation": "continue_web", "target": _THIS_TASK,
                "question": outcome.text, "ttl": PAUSE_TTL_SECONDS,
                "revise": {"capability": "web_task_guide", "operation": "guide_web", "target": _THIS_TASK},
            }
        else:
            self.task = None
        return result

    @staticmethod
    def driver():
        """The user's own browser when HARIKA's extension is connected, else HARIKA's window."""
        from app.tools.web.browser.extension_bridge import extension_bridge
        from app.tools.web.browser.driver import edge_window
        return extension_bridge if extension_bridge.connected() else edge_window

    @staticmethod
    def _fail(reason: str) -> Dict[str, Any]:
        return {"success": False, "verified": False, "error": reason}


web_task_tool = WebTaskTool()
tool_registry.register_tool(web_task_tool)
