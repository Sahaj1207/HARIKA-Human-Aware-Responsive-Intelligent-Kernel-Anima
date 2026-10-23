"""HARIKA's offline voice: "Hey HARIKA", speech to text, and a speaking voice.

One microphone stream feeds a small state machine:

    idle: the voice activity detector waits for speech; each short burst of
          speech is transcribed on this computer and ignored unless it starts
          with "Hey HARIKA" / "OK HARIKA"
      -> listening (if the wake phrase came alone, the next utterance is the request)
      -> thinking (the request goes through the normal router)
      -> speaking (Piper reads the answer, sentence by sentence)
      -> listening for a follow-up (a few seconds, no wake phrase needed) -> ... -> idle

Everything runs locally on the CPU with sherpa-onnx. Audio is processed in
memory and never written to disk; transcripts that don't start with the wake
phrase are discarded. While HARIKA speaks, the microphone only listens for the
user talking over her (her own voice coming back through the speakers is
recognised as hers and ignored); that stops her and becomes the next request.
"""
import asyncio
import json
import logging
import queue
import re
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from app.core.paths import data_path
from app.voice import models
from app.voice.models import DEFAULT_VOICE, VOICES

logger = logging.getLogger("harika.voice.engine")

SAMPLE_RATE = 16000
_BLOCK = 1600  # 0.1 s of audio per read
_LISTEN_TIMEOUT = 6.0  # seconds to start speaking after "Hey HARIKA"
_MAX_REQUEST = 15.0  # seconds
_FOLLOW_UP = 8.0  # seconds to start a follow-up after HARIKA answers, without "Hey HARIKA"
_MAX_TURNS = 12  # follow-ups in one conversation before going back to waiting for "Hey HARIKA"
_GREETINGS = {"hey", "hi", "ok", "okay", "hello"}

DEFAULT_SETTINGS = {
    "wake_word": False,          # opt-in: always-on listening is the user's choice
    "speak_replies": "voice",    # "voice" (when you talk), "always", "never"
    "voice": DEFAULT_VOICE,
    "speed": 1.0,
    "user_name": "User",
    "follow_up": True,           # keep listening briefly after answering, so the conversation can go on
    "barge_in": True,            # speaking while HARIKA talks stops her and becomes the next request
    "engine": "piper",           # "piper" (offline) or "azure" (expressive, needs a key)
    "azure_region": "",
    "azure_voice": "en-US-AriaNeural",
}

# Offline voice pace per tone (Piper has no emotional styles, so pace carries the mood).
_TONE_PACE = {"excited": 1.06, "playful": 1.04, "cheerful": 1.03, "empathetic": 0.93,
              "calm": 0.95, "apologetic": 0.95, "serious": 0.97}


def split_wake_phrase(text: str) -> Optional[str]:
    """If text starts with "(hey|ok...) HARIKA", return what follows (maybe ""); else None.

    Tolerates the small spelling variations speech recognition produces for the
    name ("Harika", "Hareeka", "Hari ka").
    """
    words = re.findall(r"[\w']+", text.lower())
    if not words:
        return None
    start = 1 if words[0] in _GREETINGS else 0
    # "harika", or a name split in two ("hari ka"): take whichever reads closest.
    best_span, best_score = 0, 0.0
    for span in (1, 2):
        candidate = "".join(words[start:start + span])
        score = SequenceMatcher(None, candidate, "harika").ratio() if candidate else 0.0
        if score >= best_score:
            best_span, best_score = span, score
    # 0.75 accepts recogniser spellings ("Harka", "Hareeka") while ordinary words
    # stay well below it ("America" 0.62, "Erica" 0.55).
    if best_score < 0.75:
        return None
    # Return the remainder with the user's original wording and punctuation.
    consumed = start + best_span
    remainder = re.split(r"[\w']+", text, maxsplit=consumed)
    return remainder[-1].lstrip(" ,.!?-").strip() if len(remainder) > consumed else ""


def split_sentences(text: str) -> List[str]:
    # A trailing "Sources: ..." line is for reading, not for saying out loud.
    text = re.sub(r"(?:^|\n)\s*Sources:[^\n]*\s*$", "", text or "")
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return [p for p in parts if p]


def is_own_voice(heard: str, saying: str) -> bool:
    """Whether a transcript heard while speaking is HARIKA's own voice from the speakers.

    Recognition of the echo is imperfect, so it counts as hers when most of its words
    are in what she is saying (or it is too short to tell).
    """
    def words(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower().replace("'", "").replace("’", ""))

    heard_words = words(heard)
    if len(heard_words) < 2:
        return True
    said = set(words(saying))
    return sum(word in said for word in heard_words) / len(heard_words) >= 0.5


class VoiceSettings:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_path("settings", "voice.json")
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(DEFAULT_SETTINGS)
            if self.path.exists():
                try:
                    stored = json.loads(self.path.read_text(encoding="utf-8"))
                    data.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
                except (OSError, json.JSONDecodeError):
                    logger.warning("[Voice] Settings unreadable; using defaults.")
            if data["voice"] not in VOICES:
                data["voice"] = DEFAULT_VOICE
            return data

    def update(self, **changes: Any) -> Dict[str, Any]:
        data = self.load()
        if "voice" in changes and changes["voice"] not in VOICES:
            raise ValueError(f"Unknown voice '{changes['voice']}'.")
        if "speak_replies" in changes and changes["speak_replies"] not in ("voice", "always", "never"):
            raise ValueError("speak_replies must be voice, always or never.")
        if "speed" in changes:
            changes["speed"] = min(1.5, max(0.7, float(changes["speed"])))
        if "engine" in changes and changes["engine"] not in ("piper", "azure"):
            raise ValueError("engine must be piper or azure.")
        if "azure_voice" in changes:
            from app.voice.azure_tts import VOICES as AZURE_VOICES
            if changes["azure_voice"] not in AZURE_VOICES:
                raise ValueError(f"Unknown Azure voice '{changes['azure_voice']}'.")
        data.update({k: v for k, v in changes.items() if k in DEFAULT_SETTINGS and v is not None})
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data


def _first(folder: Path, *patterns: str) -> str:
    for pattern in patterns:
        found = sorted(folder.glob(pattern))
        if found:
            return str(found[0])
    raise FileNotFoundError(f"No {patterns} in {folder}")


class VoiceEngine:
    def __init__(self, settings: Optional[VoiceSettings] = None):
        self.settings = settings or VoiceSettings()
        self.state = "off"
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self._interrupt = threading.Event()
        self._saying = ""  # the reply being spoken, to tell her echo from the user
        self._barged: Optional[str] = None  # what the user said over her, to handle next
        self._capture_requests: "queue.Queue[tuple]" = queue.Queue()  # (reply queue, timeout)
        self._model_lock = threading.Lock()
        self._asr = None
        self._tts: Dict[str, Any] = {}
        self.on_request: Optional[Callable[[str], Any]] = None  # async (text) -> reply text

    # ------------------------------------------------------------- models

    def ready(self) -> bool:
        """The offline models (listening and the offline voice) are downloaded."""
        return not models.missing(self.settings.load()["voice"])

    def can_speak(self) -> bool:
        """There is a voice to speak with: the offline one, or Azure when it's chosen and connected."""
        prefs = self.settings.load()
        if prefs["engine"] == "azure":
            from app.voice import azure_tts
            if prefs["azure_region"] and azure_tts.has_key():
                return True
        return self.ready()

    def _new_vad(self, min_silence: float = 0.6):
        import sherpa_onnx

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(models.model_path("vad"))
        config.silero_vad.min_silence_duration = min_silence
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.max_speech_duration = _MAX_REQUEST
        config.sample_rate = SAMPLE_RATE
        return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)

    def _load_asr(self):
        with self._model_lock:
            if self._asr is None:
                import sherpa_onnx

                folder = models.model_path("asr")
                self._asr = sherpa_onnx.OfflineRecognizer.from_moonshine_v2(
                    encoder=_first(folder, "encoder*.ort", "encoder*.onnx"),
                    decoder=_first(folder, "decoder*.ort", "decoder*.onnx"),
                    tokens=_first(folder, "tokens.txt"),
                    num_threads=2,
                )
            return self._asr

    def _load_tts(self, voice_id: str):
        with self._model_lock:
            if voice_id not in self._tts:
                import sherpa_onnx

                folder = models.voice_path(voice_id)
                vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=_first(folder, "*.onnx"),
                    tokens=str(folder / "tokens.txt"),
                    data_dir=str(folder / "espeak-ng-data"),
                )
                config = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(vits=vits, num_threads=2),
                    max_num_sentences=1,
                )
                self._tts[voice_id] = sherpa_onnx.OfflineTts(config)
            return self._tts[voice_id]

    # ------------------------------------------------------------- speech

    def transcribe(self, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
        asr = self._load_asr()
        stream = asr.create_stream()
        stream.accept_waveform(sample_rate, samples)
        asr.decode_stream(stream)
        return " ".join(stream.result.text.split())

    def synthesize(self, text: str, voice_id: Optional[str] = None, tone: Optional[str] = None):
        prefs = self.settings.load()
        if voice_id is None and prefs["engine"] == "azure":
            from app.voice.azure_tts import azure_speech
            if azure_speech.available(prefs["azure_region"]):
                try:
                    return azure_speech.synthesize(text, prefs["azure_voice"], prefs["azure_region"], tone, float(prefs["speed"]))
                except Exception as exc:
                    logger.warning(f"[Voice] Azure speech failed, using the offline voice: {exc}")
        voice_id = voice_id or prefs["voice"]
        tts = self._load_tts(voice_id)
        # Piper's speed is a length scale: higher speed setting = shorter audio.
        audio = tts.generate(text, sid=0, speed=float(prefs["speed"]) * _TONE_PACE.get(tone or "", 1.0))
        return np.asarray(audio.samples, dtype=np.float32), audio.sample_rate

    def speak(self, text: str, voice_id: Optional[str] = None, tone: Optional[str] = None) -> None:
        """Say text (blocking), generating the next sentence while the current one plays."""
        import sounddevice as sd

        sentences = split_sentences(text)[:30]
        if not sentences:
            return
        clips: "queue.Queue[Optional[tuple]]" = queue.Queue(maxsize=3)

        def produce() -> None:
            try:
                for sentence in sentences:
                    if self._interrupt.is_set():
                        break
                    clips.put(self.synthesize(sentence, voice_id, tone))
            finally:
                clips.put(None)

        self._interrupt.clear()
        self._saying = text
        self._speaking.set()
        previous = self.state
        self._set_state("speaking")
        threading.Thread(target=produce, name="harika-tts", daemon=True).start()
        try:
            while True:
                clip = clips.get()
                if clip is None or self._interrupt.is_set():
                    break
                sd.play(*clip)
                sd.wait()
        finally:
            self._speaking.clear()
            self._saying = ""
            self._set_state(previous if previous not in ("speaking",) else "idle")

    def speak_and_follow_up(self, text: str, tone: Optional[str], conversation: str) -> None:
        """Push-to-talk conversations: say the reply, then listen briefly for a follow-up.

        What is heard goes back (as a "voice_follow_up" event) to the window the
        conversation is in, which sends it like a spoken request. Stopping her, a
        pause, or the setting being off ends the conversation.
        """
        self.speak(text, tone=tone)
        if self._interrupt.is_set() or self._barged is not None:
            return  # stopped, or talked over (the "Hey HARIKA" listener takes that request)
        if not self.settings.load()["follow_up"] or not self.ready():
            return
        self._publish("voice_follow_up", conversation=conversation, phase="listening")
        try:
            heard = self.listen_once(timeout=_FOLLOW_UP).strip()
        except Exception as exc:
            logger.warning(f"[Voice] Follow-up listening failed: {exc}")
            heard = ""
        self._publish("voice_follow_up", conversation=conversation, phase="heard", text=heard)

    def stop_speaking(self) -> None:
        import sounddevice as sd

        self._interrupt.set()
        sd.stop()

    # ------------------------------------------------------------- listening

    def listen_once(self, timeout: float = _LISTEN_TIMEOUT) -> str:
        """Push-to-talk: capture one request from the microphone and transcribe it."""
        if self._thread and self._thread.is_alive():
            reply: "queue.Queue[str]" = queue.Queue()
            self._capture_requests.put((reply, timeout))
            return reply.get(timeout=timeout + _MAX_REQUEST + 10)
        import sounddevice as sd

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=_BLOCK) as mic:
            samples = self._capture(lambda: mic.read(_BLOCK)[0][:, 0], timeout)
        self._set_state("off")
        return self.transcribe(samples) if samples is not None else ""

    def _capture(self, read_block: Callable[[], np.ndarray], timeout: float) -> Optional[np.ndarray]:
        """Collect one spoken request: waits for speech, stops after a pause.

        Everything from the moment listening starts is kept, and the detector
        only decides when the request is over: its own segments trim the first
        word (it needs a moment to recognise that speech began).
        """
        vad = self._new_vad(min_silence=0.8)
        self._set_state("listening")
        recorded: List[np.ndarray] = []
        heard_speech = False
        started = time.monotonic()
        while not self._stop.is_set():
            block = read_block()
            recorded.append(block)
            vad.accept_waveform(block)
            if vad.is_speech_detected():
                heard_speech = True
            if not vad.empty():  # a complete utterance followed by a pause
                return np.concatenate(recorded)
            elapsed = time.monotonic() - started
            if not heard_speech and elapsed > timeout:
                return None
            if elapsed > timeout + _MAX_REQUEST:
                return np.concatenate(recorded) if heard_speech else None
        return None

    def start(self, loop: asyncio.AbstractEventLoop) -> bool:
        """Start the always-on wake listener (if enabled and the models are present)."""
        self._loop = loop
        if not self.settings.load()["wake_word"] or not self.ready():
            if not (self._thread and self._thread.is_alive()):
                self._set_state("off")
            return False
        if self._thread and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="harika-voice", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        self._set_state("off")

    def _run(self) -> None:
        import sounddevice as sd

        try:
            self._load_asr()
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=_BLOCK) as mic:
                read = lambda: mic.read(_BLOCK)[0][:, 0]  # noqa: E731
                vad = self._new_vad()
                barge = None
                self._set_state("idle")
                logger.info("[Voice] Listening for \"Hey HARIKA\".")
                while not self._stop.is_set():
                    # Push-to-talk requests share this microphone stream.
                    try:
                        reply, wait = self._capture_requests.get_nowait()
                    except queue.Empty:
                        reply = None
                    if reply is not None:
                        samples = self._capture(read, wait)
                        reply.put(self.transcribe(samples) if samples is not None else "")
                        vad = self._new_vad()
                        self._set_state("idle")
                        continue

                    block = read()
                    if self._speaking.is_set():
                        barge = self._listen_while_speaking(block, barge)
                        continue
                    barge = None
                    if self._barged is not None:
                        # The user talked over a reply that wasn't part of a voice conversation.
                        request, self._barged = self._barged, None
                        self._handle_wake(request, read)
                        vad = self._new_vad()
                        self._set_state("idle")
                        continue
                    vad.accept_waveform(block)
                    while not vad.empty():
                        segment = np.asarray(vad.front.samples, dtype=np.float32)
                        vad.pop()
                        request = split_wake_phrase(self.transcribe(segment))
                        if request is None:
                            continue  # not addressed to HARIKA; the transcript is discarded
                        self._handle_wake(request, read)
                        vad = self._new_vad()
                        self._set_state("idle")
                        break
        except Exception as exc:
            logger.error(f"[Voice] Listener stopped: {exc}")
            self._publish("voice_error", message=str(exc))
            self._set_state("off")

    def _handle_wake(self, request: str, read: Callable[[], np.ndarray]) -> None:
        """One voice conversation: the request, then follow-ups without "Hey HARIKA" until a pause."""
        self._publish("voice", stage="wake")
        if not request:
            # "Hey HARIKA" on its own: chime, then listen for the request.
            self._chime()
            request = self._hear(read, _LISTEN_TIMEOUT)
        if not request:
            self._publish("voice", stage="no_speech")
            return
        for _ in range(_MAX_TURNS):
            self._answer(request, read)
            if self._barged is not None:
                request, self._barged = self._barged, None  # they talked over the answer
                continue
            if not self.settings.load()["follow_up"]:
                return
            request = self._hear(read, _FOLLOW_UP)
            if not request:
                return  # a pause ends the conversation

    def _hear(self, read: Callable[[], np.ndarray], timeout: float) -> str:
        samples = self._capture(read, timeout)
        return self.transcribe(samples).strip() if samples is not None else ""

    def _answer(self, request: str, read: Callable[[], np.ndarray]) -> None:
        self._publish("voice", stage="heard", text=request)
        self._set_state("thinking")
        reply, tone = "", None
        if self.on_request and self._loop:
            future = asyncio.run_coroutine_threadsafe(self.on_request(request), self._loop)
            try:
                reply = future.result(timeout=120)
                if isinstance(reply, dict):  # {"text", "tone"} from the router
                    reply, tone = reply.get("text", ""), reply.get("tone")
            except Exception as exc:
                reply = "Sorry, something went wrong while I was working on that."
                logger.error(f"[Voice] Request failed: {exc}")
        self._publish("voice", stage="answered", text=request, reply=reply, tone=tone)
        if reply and self.settings.load()["speak_replies"] != "never":
            self._say(reply, tone, read)

    def _say(self, reply: str, tone: Optional[str], read: Callable[[], np.ndarray]) -> None:
        """Speak on another thread while this one keeps listening, so the user can talk over her."""
        done = threading.Event()

        def talk() -> None:
            try:
                self.speak(reply, tone=tone)
            finally:
                done.set()

        threading.Thread(target=talk, name="harika-say", daemon=True).start()
        vad = None
        while not done.is_set() and not self._stop.is_set():
            block = read()
            if self._speaking.is_set():
                vad = self._listen_while_speaking(block, vad)
        done.wait()

    def _listen_while_speaking(self, block: np.ndarray, vad):
        """Feed one block heard while HARIKA talks; stop her if it is the user, not her echo."""
        if not self.settings.load()["barge_in"]:
            return None
        if vad is None:
            vad = self._new_vad(min_silence=0.4)
        vad.accept_waveform(block)
        while not vad.empty():
            segment = np.asarray(vad.front.samples, dtype=np.float32)
            vad.pop()
            heard = self.transcribe(segment).strip()
            if not heard or is_own_voice(heard, self._saying):
                continue
            remainder = split_wake_phrase(heard)
            logger.info("[Voice] Interrupted by the user.")
            self.stop_speaking()
            self._barged = heard if remainder is None else remainder
            self._publish("voice", stage="interrupted")
            return None
        return vad

    def _chime(self) -> None:
        """A short two-note chime so the user knows HARIKA is listening."""
        import sounddevice as sd

        def tone(freq: float, seconds: float) -> np.ndarray:
            t = np.linspace(0, seconds, int(24000 * seconds), endpoint=False)
            envelope = np.minimum(1, np.minimum(t / 0.01, (seconds - t) / 0.06))
            return (0.18 * np.sin(2 * np.pi * freq * t) * envelope).astype(np.float32)

        self._speaking.set()
        try:
            sd.play(np.concatenate([tone(880, 0.09), tone(1320, 0.12)]), 24000)
            sd.wait()
        finally:
            self._speaking.clear()

    # ------------------------------------------------------------- events

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self._publish("voice", stage="state", state=state)

    @staticmethod
    def _publish(event: str, **payload: Any) -> None:
        from app.core.live_events import live_events
        live_events.publish(event, **payload)


voice_engine = VoiceEngine()
