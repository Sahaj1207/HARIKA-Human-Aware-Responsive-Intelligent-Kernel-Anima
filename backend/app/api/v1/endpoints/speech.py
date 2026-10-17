"""Settings > Voice and the voice controls the app uses (push-to-talk, speak).

Microphone and speaker control are only reachable from this computer.
"""
import asyncio
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.endpoints.llm_settings import local_only
from app.core.live_events import live_events
from app.voice import models
from app.voice.engine import voice_engine
from app.voice import azure_tts
from app.voice.models import VOICES

router = APIRouter(dependencies=[Depends(local_only)])

PREVIEW_TEXT = "Hi, I'm HARIKA. This is how I'll sound when I answer you."


class SpeechSettingsUpdate(BaseModel):
    wake_word: bool | None = None
    speak_replies: str | None = None
    voice: str | None = None
    speed: float | None = None
    user_name: str | None = None
    engine: str | None = None
    azure_voice: str | None = None


class AzureConnect(BaseModel):
    key: str
    region: str


class SpeakRequest(BaseModel):
    text: str
    tone: str | None = None


class PreviewRequest(BaseModel):
    voice: str


def _status() -> dict:
    settings = voice_engine.settings.load()
    return {
        "state": voice_engine.state,
        "ready": voice_engine.ready(),
        "missing_mb": models.total_missing_mb(settings["voice"]),
        "downloading": models.voice_model_download.running,
        "settings": settings,
        "can_speak": voice_engine.can_speak(),
        "azure": {
            "connected": bool(settings["azure_region"]) and azure_tts.has_key(),
            "region": settings["azure_region"],
            "voices": [{"id": key, "name": info["name"], "accent": info["accent"]} for key, info in azure_tts.VOICES.items()],
        },
        "voices": [
            {"id": key, "name": info["name"], "accent": info["accent"], "size_mb": info["size_mb"],
             "downloaded": models.voice_path(key).exists()}
            for key, info in VOICES.items()
        ],
    }


def _start_download(loop: asyncio.AbstractEventLoop, voice_id: str) -> bool:
    def progress(update: dict) -> None:
        live_events.publish("voice_models", **update)
        if update.get("status") == "done":
            # Models arrived: start listening if the user already turned it on.
            loop.call_soon_threadsafe(voice_engine.start, loop)

    return models.voice_model_download.start(progress, voice_id)


def _speak_in_background(text: str, tone: str | None = None) -> None:
    threading.Thread(target=voice_engine.speak, args=(text,), kwargs={"tone": tone}, name="harika-speak", daemon=True).start()


@router.get("")
async def speech_status():
    return _status()


@router.post("/models/download", status_code=202)
async def download_voice_models():
    if voice_engine.ready():
        return _status()
    if not _start_download(asyncio.get_running_loop(), voice_engine.settings.load()["voice"]):
        raise HTTPException(status_code=409, detail="The voice is already downloading.")
    return _status()


@router.put("/settings")
async def update_speech_settings(body: SpeechSettingsUpdate):
    try:
        voice_engine.settings.update(**body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.voice and not models.voice_path(body.voice).exists():
        _start_download(asyncio.get_running_loop(), body.voice)  # a newly chosen voice downloads itself
    if body.wake_word is not None:
        if body.wake_word:
            voice_engine.start(asyncio.get_running_loop())
        else:
            await asyncio.to_thread(voice_engine.stop)
    return _status()


@router.post("/listen")
async def listen():
    """Push-to-talk: record one request and return the words."""
    if not voice_engine.ready():
        raise HTTPException(status_code=409, detail="Download HARIKA's voice in Settings first.")
    try:
        text = await asyncio.to_thread(voice_engine.listen_once)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"I couldn't use the microphone: {exc}") from exc
    return {"text": text}


@router.put("/azure")
async def connect_azure(body: AzureConnect):
    region = body.region.strip().lower().replace(" ", "")
    try:
        await asyncio.to_thread(azure_tts.verify, body.key.strip(), region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="I couldn't reach Azure. Check your internet connection.") from exc
    azure_tts.save_key(body.key.strip())
    voice_engine.settings.update(azure_region=region, engine="azure")
    return _status()


@router.delete("/azure")
async def disconnect_azure():
    azure_tts.delete_key()
    voice_engine.settings.update(azure_region="", engine="piper")
    return _status()


@router.post("/speak", status_code=202)
async def speak(body: SpeakRequest):
    if not voice_engine.can_speak():
        raise HTTPException(status_code=409, detail="Download HARIKA's voice in Settings first.")
    _speak_in_background(body.text, body.tone)
    return {"speaking": True}


@router.post("/preview", status_code=202)
async def preview_voice(body: PreviewRequest):
    if body.voice in azure_tts.VOICES:
        settings = voice_engine.settings.load()
        if not (settings["azure_region"] and azure_tts.has_key()):
            raise HTTPException(status_code=409, detail="Connect Azure first.")

        def say() -> None:
            audio = azure_tts.azure_speech.synthesize(PREVIEW_TEXT, body.voice, settings["azure_region"], "cheerful")
            import sounddevice as sd
            sd.play(*audio)
            sd.wait()
        threading.Thread(target=say, name="harika-preview", daemon=True).start()
        return {"previewing": body.voice}
    if body.voice not in VOICES:
        raise HTTPException(status_code=400, detail="Unknown voice.")
    if not models.voice_path(body.voice).exists():
        raise HTTPException(status_code=409, detail="That voice isn't downloaded yet. Choose it to download it.")
    threading.Thread(target=voice_engine.speak, args=(PREVIEW_TEXT, body.voice), name="harika-preview", daemon=True).start()
    return {"previewing": body.voice}


@router.post("/stop")
async def stop_speaking():
    voice_engine.stop_speaking()
    return {"stopped": True}
