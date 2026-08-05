import time
import logging
from typing import Dict, Any, Optional
from app.agents.schemas import AgentTaskResult
from app.tools.manager import tool_manager
from app.tools.schemas import ActionPlan, SingleAction
from app.vision.manager import vision_manager

logger = logging.getLogger("harika.agents.executor")


class TaskExecutor:
    """Executes single plan tasks via ToolManager / VisionManager without direct LLM calls."""

    async def execute_task(
        self,
        task_id: str,
        step_number: int,
        title: str,
        tool_name: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        dry_run: bool = False
    ) -> AgentTaskResult:
        start_time = time.time()
        output: Dict[str, Any] = {}
        error: Optional[str] = None
        success = True

        logger.info(f"[TaskExecutor] Executing step {step_number} ('{title}') tool='{tool_name}'.")

        try:
            # 1. Vision asset processing if visual file supplied
            if file_bytes and filename:
                if filename.lower().endswith(".pdf"):
                    v_res = vision_manager.process_pdf(file_bytes, filename, "application/pdf")
                else:
                    v_res = vision_manager.process_image(file_bytes, filename, "image/png")
                output["vision_result"] = v_res.model_dump()
            # 2. Tool action execution via ToolManager (Never calling LLM directly)
            elif tool_name:
                tool = tool_manager.registry.get_tool(tool_name)
                if not tool:
                    success = False
                    error = f"Tool '{tool_name}' is not registered in Action Engine."
                else:
                    action_plan = ActionPlan(
                        is_tool_action=True,
                        actions=[SingleAction(tool_name=tool_name, arguments=arguments or {}, reasoning="Agent task execution.")],
                        confidence=1.0
                    )
                    tool_res = await tool_manager.execute_planned_action(action_plan, dry_run=dry_run)
                    if tool_res and tool_res.success:
                        output = tool_res.output if isinstance(tool_res.output, dict) else {"result": tool_res.output}
                    else:
                        success = False
                        error = tool_res.error if tool_res else "Tool execution produced no result."

            else:
                # Conversational or cognitive step
                output = {"info": f"Completed cognitive step '{title}'."}

        except Exception as e:
            success = False
            error = str(e)
            logger.error(f"[TaskExecutor] Error executing task '{title}': {e}")

        duration = round((time.time() - start_time) * 1000, 2)
        return AgentTaskResult(
            task_id=task_id,
            step_number=step_number,
            title=title,
            tool_name=tool_name,
            success=success,
            output=output,
            error=error,
            duration_ms=duration,
            retry_count=0
        )


task_executor = TaskExecutor()
