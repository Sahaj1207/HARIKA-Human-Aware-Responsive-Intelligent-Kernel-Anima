from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.router.manager import router_manager

router = APIRouter()


@router.post("/tasks/stop")
async def stop_task():
    """Stops a multi-step task between steps (the Stop button while HARIKA works)."""
    from app.tools.productivity.task_tool import task_tool
    from app.tools.web.web_task_tool import web_task_tool
    stopping = task_tool.stop()
    return {"stopping": web_task_tool.stop() or stopping}


@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(request: ChatRequest):
    """
    POST /api/v1/chat
    Processes incoming user directive through the HARIKA Cognitive Router.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message string cannot be empty.")

    result = await router_manager.route_request(
        message=request.message.strip(),
        user_id=request.user_name or "default",
        conversation_history=request.conversation_history,
        spoken=request.spoken,
    )

    return ChatResponse(
        response=result["response"],
        provider=result.get("provider", "router-v1.0"),
        model=result.get("model", "cognitive-router"),
        latency_ms=int(round(result["latency_ms"])),
        tone=result.get("tone") or "warm",
        learned=result.get("learned") or [],
    )


