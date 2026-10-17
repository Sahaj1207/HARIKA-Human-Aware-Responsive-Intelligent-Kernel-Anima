"""Tasks that take several steps: research, comparisons, plans. See app/agents/task_agent.py."""
from typing import Any, Dict, Optional, Tuple

from app.tools.base_tool import BaseTool
from app.tools.registry import tool_registry
from app.tools.schemas import PermissionLevel, ToolHealth, ToolManifest


class TaskTool(BaseTool):
    manifest = ToolManifest(
        name="tasks",
        display_name="Tasks",
        description="Works through multi-step goals (research and compare, plan a trip, find a free slot) and writes up the result.",
        version="1.0.0",
        author="HARIKA OS Core",
        category="productivity",
        permissions=PermissionLevel.LOW,
        enabled=True,
        platforms=["windows", "linux", "darwin"],
        capabilities=["run_task"],
        operations={"task": "run_task"},
        free_text_operations=["task"],
        ability="work through bigger tasks: research and compare, plan trips, find time in your calendar",
        target_description="the whole goal in the user's words, self-contained (e.g. 'compare 3 laptops under 60000 rupees for coding')",
    )
    timeout_seconds = 420.0

    def __init__(self):
        self.current = None

    def health_check(self) -> ToolHealth:
        return ToolHealth(available=True, reason="Uses web, calendar, email and notes skills", dependencies=[])

    def match_target(self, requested: str, operation: Optional[str] = None) -> Tuple[Optional[str], float]:
        text = (requested or "").strip()
        return (text, 0.7) if text else (None, 0.0)

    def describe_action(self, args: Dict[str, Any]) -> str:
        return f"work on: {args.get('target') or 'your task'}"

    def stop(self) -> bool:
        if self.current is None:
            return False
        self.current.stop_requested = True
        return True

    async def execute(self, args: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        from app.agents.task_agent import TaskAgent, TaskStopped, save_report
        from app.core.live_events import live_events
        from app.tools import recent_results

        goal = str(args.get("target") or args.get("request") or "").strip()
        if not goal:
            return {"success": False, "verified": False, "error": "What should I work on?"}
        if dry_run:
            return {"dry_run": True, "action": "run_task", "goal": goal}

        agent = TaskAgent(progress=lambda text: live_events.publish("activity", text=text, stoppable=True))
        self.current = agent
        try:
            result = await agent.run(goal)
        except TaskStopped:
            return {"action": "run_task", "success": True, "verified": True, "tone": "calm",
                    "summary": "Okay, I stopped.", "error": None}
        finally:
            self.current = None
            live_events.publish("activity", text="", stoppable=False)

        summary = result["answer"]
        if result["report"] or len(result["steps"]) >= 2:
            path = save_report(result["title"], goal, result["report"], result["answer"], result["steps"])
            recent_results.remember("files", [{"path": str(path), "title": path.name}])
            summary += f"\n\nI saved the details to Documents\\HARIKA\\{path.name}. Say “open it” to see them."
        outcome: Dict[str, Any] = {"action": "run_task", "steps": result["steps"], "success": True, "verified": True,
                                   "summary": summary, "error": None}
        confirmation = self._follow_up(result.get("follow_up"))
        if confirmation:
            outcome["summary"] += f"\n\n{confirmation['question']}"
            outcome["confirmation"] = confirmation
        return outcome

    @staticmethod
    def _follow_up(proposal: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """A proposed action becomes an ordinary capability step that waits for the user's yes."""
        if not proposal:
            return None
        from app.tools.capability_resolver import capability_resolver
        operation, target = str(proposal.get("operation", "")), str(proposal.get("target", "")).strip()
        resolution = capability_resolver.resolve_operation(operation, target)
        if not resolution.supported or not target:
            return None
        parameters = proposal.get("parameters") if isinstance(proposal.get("parameters"), dict) else {}
        question = str(proposal.get("question") or "").strip() or f"Should I {operation} “{target}”?"
        return {"capability": resolution.capability, "operation": operation, "target": resolution.target,
                "parameters": parameters, "question": question}


task_tool = TaskTool()
tool_registry.register_tool(task_tool)
