import logging
from typing import Dict, List, Any, Optional
from app.tools.registry import tool_registry, ToolRegistry
from app.tools.planner import action_planner, ActionPlanner
from app.tools.executor import tool_executor, ToolExecutor
from app.tools.result import ToolResult
from app.tools.schemas import ActionPlan, ToolMetrics, ToolStatusCode

logger = logging.getLogger("harika.tools.manager")


class ToolManager:
    """Central Facade Entry Point orchestrating Tool Capabilities, Planning, Execution, Metrics, and MCP readiness."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        planner: Optional[ActionPlanner] = None,
        executor: Optional[ToolExecutor] = None,
    ):
        self.registry = registry or tool_registry
        self.planner = planner or action_planner
        self.executor = executor or tool_executor

    def get_capabilities(self) -> List[Dict[str, Any]]:
        """Returns metadata capabilities manifest for all registered tools."""
        return [tool.to_schema() for tool in self.registry.list_tools()]

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.executor.get_history(limit=limit)

    def get_metrics(self) -> ToolMetrics:
        history = self.executor.get_history(limit=100)
        tools = self.registry.list_tools()
        
        total_tools = len(tools)
        enabled_tools = sum(1 for t in tools if t.manifest.enabled)
        total_executions = len(history)

        if total_executions == 0:
            return ToolMetrics(
                total_tools=total_tools,
                enabled_tools=enabled_tools,
                total_executions=0,
                success_rate=100.0,
                failure_rate=0.0,
                average_duration_ms=0.0,
                most_used_tool=None
            )

        successes = sum(1 for h in history if h.get("success"))
        success_rate = round((successes / total_executions) * 100, 1)
        failure_rate = round(100.0 - success_rate, 1)

        total_dur = sum(h.get("execution_time_ms", 0.0) for h in history)
        avg_dur = round(total_dur / total_executions, 2)

        tool_counts: Dict[str, int] = {}
        for h in history:
            name = h.get("tool_name", "unknown")
            tool_counts[name] = tool_counts.get(name, 0) + 1

        most_used = max(tool_counts, key=tool_counts.get) if tool_counts else None

        return ToolMetrics(
            total_tools=total_tools,
            enabled_tools=enabled_tools,
            total_executions=total_executions,
            success_rate=success_rate,
            failure_rate=failure_rate,
            average_duration_ms=avg_dur,
            most_used_tool=most_used
        )

    def plan_action(self, user_message: str) -> ActionPlan:
        return self.planner.plan_action(user_message)

    async def execute_planned_action(self, plan: ActionPlan, dry_run: bool = False) -> Optional[ToolResult]:
        if not plan.is_tool_action or not plan.actions:
            return None

        # Execute only the first action for Sprint 9 (Architecture supports multi-action list)
        action = plan.actions[0]
        tool = self.registry.get_tool(action.tool_name)

        if not tool:
            return ToolResult(
                success=False,
                status_code=ToolStatusCode.NOT_INSTALLED,
                tool_name=action.tool_name,
                error=f"Tool '{action.tool_name}' is not registered."
            )

        return await self.executor.execute_tool(tool, action.arguments, dry_run=dry_run)


tool_manager = ToolManager()
