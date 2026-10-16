from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.live_events import live_events

router = APIRouter()


@router.get("/events")
async def stream_events():
    """
    GET /api/v1/events
    Server-Sent Events: step progress while HARIKA acts, and due reminders.
    """
    return StreamingResponse(
        live_events.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
