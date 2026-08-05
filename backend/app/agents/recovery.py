import logging
from typing import Dict, Any, Optional, List
from app.agents.schemas import AgentTaskResult
from app.agents.executor import task_executor, TaskExecutor
from app.tools.manager import tool_manager

logger = logging.getLogger("harika.agents.recovery")


class RecoveryEngine:
    """Handles task failures via retry loops, alternative tool selection, and clarification fallback."""

    def __init__(self, max_retries: int = 3, executor: Optional[TaskExecutor] = None):
        self.max_retries = max_retries
        self.executor = executor or task_executor

    def find_alternative_tool(self, current_tool: Optional[str]) -> Optional[str]:
        if not current_tool:
            return None
        tools = tool_manager.registry.list_tools()
        for t in tools:
            name = t.manifest.name
            if name != current_tool and t.manifest.enabled:
                logger.info(f"[RecoveryEngine] Found alternative tool '{name}' for failed tool '{current_tool}'.")
                return name
        return None

    async def execute_with_recovery(
        self,
        task_id: str,
        step_number: int,
        title: str,
        tool_name: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None
    ) -> AgentTaskResult:
        retries = 0
        current_tool = tool_name

        while retries <= self.max_retries:
            res = await self.executor.execute_task(
                task_id=task_id,
                step_number=step_number,
                title=title,
                tool_name=current_tool,
                arguments=arguments,
                file_bytes=file_bytes,
                filename=filename
            )
            res.retry_count = retries

            if res.success:
                if retries > 0:
                    logger.info(f"[RecoveryEngine] Task '{title}' succeeded after {retries} retry attempt(s).")
                return res

            retries += 1
            logger.warning(f"[RecoveryEngine] Task '{title}' failed (attempt {retries}/{self.max_retries + 1}): {res.error}")

            # Try alternative tool if available on retry #2
            if retries == 2 and current_tool:
                alt_tool = self.find_alternative_tool(current_tool)
                if alt_tool:
                    logger.info(f"[RecoveryEngine] Switching tool from '{current_tool}' to alternative '{alt_tool}'.")
                    current_tool = alt_tool

        logger.error(f"[RecoveryEngine] Task '{title}' exhausted max retries ({self.max_retries}). Marking failed gracefully.")
        res.error = f"Exhausted max retries ({self.max_retries}). Last error: {res.error}"
        return res


recovery_engine = RecoveryEngine()
