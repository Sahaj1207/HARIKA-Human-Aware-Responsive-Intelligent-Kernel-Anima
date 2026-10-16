import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.tools.base_tool import BaseTool
from app.tools.result import ToolResult
from app.tools.schemas import ToolStatusCode, PermissionLevel
from app.tools.permissions import permission_engine, PermissionEngine
from app.tools.events import tool_event_bus, ToolEventType

logger = logging.getLogger("harika.tools.executor")


class ToolExecutor:
    """Safely executes Tool Plugins with single concurrency lock, timeouts, audit logs, and event publication."""

    def __init__(self, history_file: Optional[Path] = None):
        self._execution_lock = asyncio.Lock()
        self.history_file = history_file or (Path(__file__).resolve().parent.parent.parent / "data" / "tools" / "history.json")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict[str, Any]] = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[ToolExecutor] Error reading history file: {e}")
            return []

    def _save_history(self) -> None:
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-100:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[ToolExecutor] Error saving history file: {e}")

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.history[-limit:]))

    async def execute_tool(
        self,
        tool: BaseTool,
        args: Dict[str, Any],
        dry_run: bool = False,
        permissions: Optional[PermissionEngine] = None,
        confirmed: bool = False
    ) -> ToolResult:
        perm_engine = permissions or permission_engine
        tool_name = tool.manifest.name

        # 1. Single Execution Concurrency Lock
        if self._execution_lock.locked():
            logger.warning(f"[ToolExecutor] Execution locked. Rejecting tool '{tool_name}' with TOOL_BUSY.")
            return ToolResult(
                success=False,
                status_code=ToolStatusCode.TOOL_BUSY,
                tool_name=tool_name,
                error="Another tool execution is currently in progress.",
                tool_version=tool.manifest.version
            )

        async with self._execution_lock:
            # 2. Check enabled state
            if not tool.manifest.enabled:
                return ToolResult(
                    success=False,
                    status_code=ToolStatusCode.TOOL_DISABLED,
                    tool_name=tool_name,
                    error=f"Tool '{tool_name}' is currently disabled.",
                    tool_version=tool.manifest.version
                )

            # 3. Check health & dependencies
            health = tool.health_check()
            if not health.available:
                return ToolResult(
                    success=False,
                    status_code=ToolStatusCode.NOT_INSTALLED,
                    tool_name=tool_name,
                    error=f"Tool dependency unavailable: {health.reason}",
                    tool_version=tool.manifest.version
                )

            # 4. Evaluate Security Permissions
            is_permitted, needs_prompt, perm_reason = perm_engine.evaluate(tool_name, tool.permission_for(args))
            if is_permitted and needs_prompt and not confirmed and not dry_run:
                # Defense in depth: the router asks the user first; nothing else may skip that.
                return ToolResult(
                    success=False,
                    status_code=ToolStatusCode.CONFIRMATION_REQUIRED,
                    tool_name=tool_name,
                    error=f"This action needs your confirmation first: {tool.describe_action(args)}.",
                    tool_version=tool.manifest.version
                )
            if not is_permitted:
                return ToolResult(
                    success=False,
                    status_code=ToolStatusCode.PERMISSION_DENIED,
                    tool_name=tool_name,
                    error=f"Permission denied: {perm_reason}",
                    tool_version=tool.manifest.version
                )

            # 5. Argument Validation BEFORE execution
            is_valid, val_error = tool.validate(args)
            if not is_valid:
                return ToolResult(
                    success=False,
                    status_code=ToolStatusCode.INVALID_ARGUMENT,
                    tool_name=tool_name,
                    error=f"Argument validation failed: {val_error}",
                    tool_version=tool.manifest.version
                )

            # Emit ToolStarted event
            tool_event_bus.emit(ToolEventType.TOOL_STARTED, {"tool_name": tool_name, "args": args, "dry_run": dry_run})

            start_time = time.perf_counter()
            try:
                # 6. Execute with Timeout Enforcement
                raw_output = await asyncio.wait_for(
                    tool.execute(args, dry_run=dry_run),
                    timeout=tool.timeout_seconds
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

                is_dict = isinstance(raw_output, dict)
                out_success = raw_output.get("success", True) if is_dict else True
                out_verified = raw_output.get("verified", out_success) if is_dict else True
                out_pid = raw_output.get("pid") if is_dict else None
                out_pname = raw_output.get("process_name") if is_dict else None
                out_err = raw_output.get("error") if is_dict else None
                out_msg = raw_output.get("message") if is_dict else None

                result = ToolResult(
                    success=out_success,
                    verified=out_verified,
                    pid=out_pid,
                    process_name=out_pname,
                    status_code=ToolStatusCode.SUCCESS if out_success else ToolStatusCode.EXECUTION_FAILED,
                    tool_name=tool_name,
                    execution_time_ms=duration_ms,
                    output=raw_output,
                    error=out_err,
                    message=out_msg or (f"Tool '{tool_name}' executed and verified successfully." if out_verified else f"Tool '{tool_name}' execution could not be verified."),
                    tool_version=tool.manifest.version,
                    metadata={"dry_run": dry_run}
                )



                tool_event_bus.emit(ToolEventType.TOOL_COMPLETED, result.model_dump())
                self.history.append(result.model_dump())
                self._save_history()
                return result

            except asyncio.TimeoutError:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                result = ToolResult(
                    success=False,
                    status_code=ToolStatusCode.TIMEOUT,
                    tool_name=tool_name,
                    execution_time_ms=duration_ms,
                    error=f"Execution timed out after {tool.timeout_seconds} seconds.",
                    tool_version=tool.manifest.version
                )
                tool_event_bus.emit(ToolEventType.TOOL_FAILED, result.model_dump())
                self.history.append(result.model_dump())
                self._save_history()
                return result

            except Exception as e:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                result = ToolResult(
                    success=False,
                    status_code=ToolStatusCode.EXECUTION_FAILED,
                    tool_name=tool_name,
                    execution_time_ms=duration_ms,
                    error=f"Tool error: {str(e)}",
                    tool_version=tool.manifest.version
                )
                tool_event_bus.emit(ToolEventType.TOOL_FAILED, result.model_dump())
                self.history.append(result.model_dump())
                self._save_history()
                return result


tool_executor = ToolExecutor()
