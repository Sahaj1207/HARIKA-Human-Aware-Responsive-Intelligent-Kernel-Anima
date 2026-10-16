"""Offline voice models (sherpa-onnx): what's needed, where it lives, and
downloading it on first use with progress shown in the app.

All models are open source and run on the CPU:
- Silero VAD (MIT): finds where speech starts and stops
- Moonshine base, English (MIT): speech to text (also used to hear "Hey HARIKA")
- Piper voices (MIT, per-voice licences in each folder): HARIKA's speaking voice,
  about 7x faster than real time on a laptop CPU
"""
import bz2
import logging
import shutil
import tarfile
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import httpx

from app.core.paths import data_path

logger = logging.getLogger("harika.voice.models")

_RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"


@dataclass(frozen=True)
class VoiceModel:
    key: str
    label: str
    url: str
    size_mb: float
    folder: str  # directory (or file, for single-file models) under models/


BASE_MODELS: List[VoiceModel] = [
    VoiceModel("vad", "Speech detection", f"{_RELEASES}/asr-models/silero_vad.onnx", 0.6, "silero_vad.onnx"),
    VoiceModel("asr", "Speech recognition",
               f"{_RELEASES}/asr-models/sherpa-onnx-moonshine-base-en-quantized-2026-02-27.tar.bz2", 111.3,
               "sherpa-onnx-moonshine-base-en-quantized-2026-02-27"),
]

# Curated Piper voices: id -> (display name, accent, piper voice name, size in MB).
VOICES: Dict[str, Dict] = {
    "amy": {"name": "Amy", "accent": "American", "piper": "en_US-amy-medium", "size_mb": 67.2},
    "kristin": {"name": "Kristin", "accent": "American", "piper": "en_US-kristin-medium", "size_mb": 67.3},
    "hannah": {"name": "Hannah", "accent": "American", "piper": "en_US-hfc_female-medium", "size_mb": 67.2},
    "jenny": {"name": "Jenny", "accent": "British", "piper": "en_GB-jenny_dioco-medium", "size_mb": 67.2},
    "cori": {"name": "Cori", "accent": "British", "piper": "en_GB-cori-medium", "size_mb": 67.3},
    "alba": {"name": "Alba", "accent": "Scottish", "piper": "en_GB-alba-medium", "size_mb": 67.2},
    "ryan": {"name": "Ryan", "accent": "American", "piper": "en_US-ryan-medium", "size_mb": 67.2},
    "alan": {"name": "Alan", "accent": "British", "piper": "en_GB-alan-medium", "size_mb": 67.2},
}
DEFAULT_VOICE = "amy"


def voice_model(voice_id: str) -> VoiceModel:
    info = VOICES.get(voice_id, VOICES[DEFAULT_VOICE])
    folder = f"vits-piper-{info['piper']}"
    return VoiceModel(f"voice:{voice_id}", f"{info['name']}'s voice", f"{_RELEASES}/tts-models/{folder}.tar.bz2",
                      info["size_mb"], folder)


def required(voice_id: str) -> List[VoiceModel]:
    return [*BASE_MODELS, voice_model(voice_id)]


def models_dir() -> Path:
    return data_path("models")


def model_path(key: str) -> Path:
    model = next(m for m in BASE_MODELS if m.key == key)
    return models_dir() / model.folder


def voice_path(voice_id: str) -> Path:
    return models_dir() / voice_model(voice_id).folder


def missing(voice_id: str = DEFAULT_VOICE) -> List[VoiceModel]:
    return [m for m in required(voice_id) if not (models_dir() / m.folder).exists()]


def total_missing_mb(voice_id: str = DEFAULT_VOICE) -> float:
    return round(sum(m.size_mb for m in missing(voice_id)), 1)


class VoiceModelDownload:
    """Downloads missing models one at a time; reports overall progress."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self.error: Optional[str] = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, on_progress: Callable[[Dict], None], voice_id: str = DEFAULT_VOICE) -> bool:
        if self.running:
            return False
        self.error = None
        self._thread = threading.Thread(target=self._run, args=(on_progress, voice_id), name="harika-voice-models", daemon=True)
        self._thread.start()
        return True

    def _run(self, on_progress: Callable[[Dict], None], voice_id: str) -> None:
        todo = missing(voice_id)
        total = sum(m.size_mb for m in todo) * 1e6 or 1
        done = 0.0
        try:
            models_dir().mkdir(parents=True, exist_ok=True)
            for model in todo:
                done = self._fetch(model, done, total, on_progress)
            on_progress({"status": "done", "percent": 100})
        except Exception as exc:
            self.error = str(exc)
            logger.warning(f"[Voice] Model download failed: {exc}")
            on_progress({"status": "failed", "error": str(exc), "percent": None})

    def _fetch(self, model: VoiceModel, done: float, total: float, on_progress) -> float:
        partial = models_dir() / f".{model.folder}.part"
        last_percent = -1
        start_done = done
        for attempt in range(5):
            # Resume from what's already on disk: slow or flaky connections stall.
            have = partial.stat().st_size if partial.exists() else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            try:
                with httpx.stream("GET", model.url, headers=headers, follow_redirects=True,
                                  timeout=httpx.Timeout(120.0, connect=20.0)) as reply:
                    if reply.status_code == 416:  # already complete
                        break
                    reply.raise_for_status()
                    resumed = reply.status_code == 206
                    done = start_done + (have if resumed else 0)
                    with open(partial, "ab" if resumed else "wb") as out:
                        for chunk in reply.iter_bytes(1 << 16):
                            out.write(chunk)
                            done += len(chunk)
                            percent = min(99, int(done * 100 / total))
                            if percent != last_percent:
                                last_percent = percent
                                on_progress({"status": f"Downloading {model.label.lower()}", "percent": percent})
                break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 4:
                    raise RuntimeError(f"the download of {model.label.lower()} kept stalling ({exc})") from exc
                logger.info(f"[Voice] {model.key} download stalled, resuming (attempt {attempt + 2})")
                on_progress({"status": f"Connection slow, resuming {model.label.lower()}", "percent": last_percent})
                # Wait longer each time so a short outage doesn't use up every retry.
                time.sleep((5, 15, 30, 60)[attempt])
        target = models_dir() / model.folder
        if model.url.endswith(".tar.bz2"):
            on_progress({"status": f"Unpacking {model.label.lower()}", "percent": last_percent})
            staging = models_dir() / f".{model.folder}.unpack"
            shutil.rmtree(staging, ignore_errors=True)
            with bz2.open(partial) as stream, tarfile.open(fileobj=stream, mode="r|") as archive:
                archive.extractall(staging, filter="data")  # refuses paths outside the folder
            extracted = staging / model.folder
            (extracted if extracted.exists() else staging).rename(target)
            shutil.rmtree(staging, ignore_errors=True)
            partial.unlink(missing_ok=True)
        else:
            partial.rename(target)
        logger.info(f"[Voice] Installed {model.key} -> {target}")
        return done


voice_model_download = VoiceModelDownload()
