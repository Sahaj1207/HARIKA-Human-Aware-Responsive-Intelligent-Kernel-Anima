from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.cognition.manager import cognition_manager

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(request: ChatRequest):
    """
    POST /api/v1/chat
    Processes incoming user directive through the Cognition Engine.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message string cannot be empty.")

    result = await cognition_manager.process_chat(
        message=request.message.strip(),
        user_name=request.user_name,
        conversation_history=request.conversation_history
    )

    return ChatResponse(
        response=result["response"],
        provider=result["provider"],
        model=result["model"],
        latency_ms=result["latency_ms"]
    )
