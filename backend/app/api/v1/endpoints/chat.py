from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.router.manager import router_manager

router = APIRouter()


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
    )


