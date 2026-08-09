from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.voice.manager import voice_manager
from app.voice.history import voice_history_manager
from app.voice.metrics import voice_metrics_manager
from app.voice.interrupt import interruption_engine
from app.voice.schemas import VoiceSession, VoiceMetrics, VoiceInterruptionPayload

router = APIRouter()


class StartVoiceSessionPayload(BaseModel):
    continuous: bool = Field(default=False)
    user_id: str = Field(default="default")


class VoiceDirectivePayload(BaseModel):
    voice_text: str = Field(..., example="Calculate 50 * 2")


@router.get("", response_model=Dict[str, Any])
async def get_voice_status():
    """Returns active voice state, current session info, and health status."""
    return voice_manager.health_check()


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_voice_history(limit: int = Query(default=20, ge=1, le=100)):
    """Returns persistent voice session history log."""
    return voice_history_manager.get_history(limit=limit)


@router.get("/metrics", response_model=VoiceMetrics)
async def get_voice_metrics():
    """Returns Voice Engine analytics, latency metrics, and interruption stats."""
    return voice_metrics_manager.get_metrics()


@router.post("/start", response_model=Dict[str, Any])
async def start_voice_session(payload: StartVoiceSessionPayload):
    """Starts a voice interaction session (single or continuous mode)."""
    try:
        session = voice_manager.start_session(continuous=payload.continuous, user_id=payload.user_id)
        return {"status": "started", "session": session.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop", response_model=Dict[str, Any])
async def stop_voice_session():
    """Stops the active voice session and saves structured session summary in Cognitive Memory."""
    try:
        session = voice_manager.stop_session()
        return {"status": "stopped", "session": session.model_dump() if session else None}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/interruption", response_model=VoiceInterruptionPayload)
async def trigger_interruption():
    """Triggers an immediate speech interruption, stopping TTS playback and clearing SpeechQueue."""
    try:
        return interruption_engine.handle_interruption()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/directive", response_model=Dict[str, Any])
async def process_directive(payload: VoiceDirectivePayload):
    """Processes a text directive received via STT speech recognition."""
    try:
        return await voice_manager.process_voice_directive(payload.voice_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
