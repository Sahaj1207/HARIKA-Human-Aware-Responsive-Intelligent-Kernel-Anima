from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.tools.manager import tool_manager
from app.tools.result import ToolResult
from app.tools.schemas import ToolMetrics, ToolStatusCode

router = APIRouter()


class DirectExecutePayload(BaseModel):
    tool_name: str = Field(..., example="calculator")
    arguments: Dict[str, Any] = Field(default_factory=dict, example={"expression": "25 * 18"})
    dry_run: bool = False


class ToggleToolPayload(BaseModel):
    enabled: bool = True


@router.get("", response_model=List[Dict[str, Any]])
async def list_tools():
    """Returns capabilities manifest for all registered tool plugins."""
    return tool_manager.get_capabilities()


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_tool_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns tool execution history log."""
    return tool_manager.get_history(limit=limit)


@router.get("/metrics", response_model=ToolMetrics)
async def get_tool_metrics():
    """Returns Action Engine analytics and performance metrics."""
    return tool_manager.get_metrics()


@router.post("/execute", response_model=ToolResult)
async def execute_tool(payload: DirectExecutePayload):
    """Executes a registered tool directly or evaluates dry-run prediction."""
    tool = tool_manager.registry.get_tool(payload.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{payload.tool_name}' not found.")

    return await tool_manager.executor.execute_tool(tool, payload.arguments, dry_run=payload.dry_run)


@router.put("/{name}/toggle")
async def toggle_tool(name: str, payload: ToggleToolPayload):
    """Enables or disables a specific tool plugin."""
    success = tool_manager.registry.toggle_tool(name, payload.enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found.")
    return {"status": "success", "tool_name": name, "enabled": payload.enabled}
