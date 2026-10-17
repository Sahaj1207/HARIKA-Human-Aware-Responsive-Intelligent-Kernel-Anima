"""Expressive speech from Azure AI Speech (neural voices with speaking styles).

The reply's tone picks a speaking style the chosen voice supports ("cheerful",
"empathetic", ...), sent as SSML. The text is XML-escaped, so it can only ever be
spoken, never interpreted as markup. The key lives in the OS credential store.
"""
import io
import time
import wave
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

import httpx
import numpy as np

from app.cognition.llm import secrets

_KEY = "azure:speech_key"

# Voices with speaking styles; styles listed in order of preference per tone below.
VOICES: Dict[str, Dict[str, object]] = {
    "en-US-AriaNeural": {"name": "Aria", "accent": "American",
                         "styles": ["chat", "cheerful", "empathetic", "excited", "friendly", "hopeful", "sad", "whispering"]},
    "en-US-JennyNeural": {"name": "Jenny", "accent": "American",
                          "styles": ["assistant", "chat", "cheerful", "excited", "friendly", "hopeful", "sad", "whispering"]},
    "en-IN-NeerjaNeural": {"name": "Neerja", "accent": "Indian", "styles": ["cheerful", "empathetic"]},
    "en-GB-SoniaNeural": {"name": "Sonia", "accent": "British", "styles": ["cheerful", "sad"]},
}
DEFAULT_VOICE = "en-US-AriaNeural"

# tone -> (preferred styles, style strength, speaking rate)
_TONES: Dict[str, Tuple[List[str], float, str]] = {
    "warm": (["friendly", "chat", "cheerful"], 0.8, "0%"),
    "cheerful": (["cheerful", "friendly"], 1.0, "+3%"),
    "excited": (["excited", "cheerful"], 1.2, "+6%"),
    "playful": (["cheerful", "friendly"], 1.1, "+4%"),
    "empathetic": (["empathetic", "friendly", "hopeful"], 1.0, "-8%"),
    "calm": (["chat", "friendly"], 0.7, "-5%"),
    "apologetic": (["empathetic", "friendly"], 0.8, "-4%"),
    "serious": ([], 1.0, "-2%"),
    "neutral": ([], 1.0, "0%"),
}


def style_for(voice: str, tone: Optional[str]) -> Tuple[Optional[str], float, str]:
    preferred, degree, rate = _TONES.get(tone or "warm", _TONES["warm"])
    supported = VOICES.get(voice, {}).get("styles", [])
    style = next((s for s in preferred if s in supported), None)
    return style, degree, rate


def ssml(text: str, voice: str, tone: Optional[str], speed: float = 1.0) -> str:
    style, degree, rate = style_for(voice, tone)
    if speed != 1.0:
        rate = f"{round((speed - 1) * 100) + int(rate.rstrip('%')):+d}%"
    language = voice[:5]
    body = f'<prosody rate="{rate}">{escape(text)}</prosody>'
    if style:
        body = f'<mstts:express-as style="{style}" styledegree="{degree}">{body}</mstts:express-as>'
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{language}">'
            f'<voice name="{voice}">{body}</voice></speak>')


def has_key() -> bool:
    return bool(secrets.get_secret(_KEY))


def save_key(key: str) -> None:
    secrets.set_secret(_KEY, key)


def delete_key() -> None:
    secrets.delete_secret(_KEY)


def verify(key: str, region: str) -> None:
    """Raises if Azure doesn't accept this key for this region."""
    reply = httpx.get(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
                      headers={"Ocp-Apim-Subscription-Key": key}, timeout=15)
    if reply.status_code == 401:
        raise ValueError("Azure rejected that key. Copy Key 1 from your Speech resource's Keys and Endpoint page.")
    if reply.status_code >= 400:
        raise ValueError(f"Azure answered with {reply.status_code}. Check the region (for example centralindia).")


class AzureSpeech:
    """Synthesizes one sentence at a time; a failure makes the caller fall back to the offline voice."""

    def __init__(self):
        self._failed_at = 0.0

    def available(self, region: str) -> bool:
        return bool(region) and has_key() and time.time() - self._failed_at > 60

    def synthesize(self, text: str, voice: str, region: str, tone: Optional[str], speed: float = 1.0):
        try:
            reply = httpx.post(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                content=ssml(text, voice, tone, speed).encode("utf-8"),
                headers={"Ocp-Apim-Subscription-Key": secrets.get_secret(_KEY) or "",
                         "Content-Type": "application/ssml+xml",
                         "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                         "User-Agent": "HARIKA"},
                timeout=15,
            )
            reply.raise_for_status()
        except Exception:
            self._failed_at = time.time()
            raise
        with wave.open(io.BytesIO(reply.content)) as clip:
            frames = clip.readframes(clip.getnframes())
            rate = clip.getframerate()
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0, rate


azure_speech = AzureSpeech()
