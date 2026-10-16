"""Voice engine logic: wake phrase, request handling, settings and API guards.

No microphone, speakers or models are used: audio I/O, speech recognition
and synthesis are faked.
"""
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.voice.engine import VoiceEngine, VoiceSettings, split_sentences, split_wake_phrase


class WakePhraseTests(unittest.TestCase):
    def test_wake_with_request_in_one_breath(self):
        self.assertEqual(split_wake_phrase("Hey, harika, open note bed for me."), "open note bed for me.")
        self.assertEqual(split_wake_phrase("OK Harika what time is it?"), "what time is it?")
        self.assertEqual(split_wake_phrase("Harika, continue this chat."), "continue this chat.")

    def test_wake_alone(self):
        for text in ("Hey Harika.", "Hey, Harka.", "hey hareeka", "Okay Harika!"):
            self.assertEqual(split_wake_phrase(text), "", text)

    def test_split_name_is_recognised(self):
        self.assertEqual(split_wake_phrase("Hey Hari ka, mute"), "mute")

    def test_ordinary_speech_is_ignored(self):
        for text in ("I had a great day today.", "Hey Erica, how are you?", "America is big", "", "hey"):
            self.assertIsNone(split_wake_phrase(text), text)

    def test_sentences_for_streaming_speech(self):
        self.assertEqual(split_sentences("It's 6 PM.  Want a reminder? Sure!"), ["It's 6 PM.", "Want a reminder?", "Sure!"])


class EngineRequestTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="harika-voice-")
        self.engine = VoiceEngine(VoiceSettings(Path(self.dir.name) / "voice.json"))
        self.events = []
        self.publish = patch.object(VoiceEngine, "_publish", side_effect=lambda event, **p: self.events.append((event, p)))
        self.publish.start()
        self.spoken = []
        self.engine.speak = lambda text, voice_id=None: self.spoken.append(text)
        self.engine._chime = lambda: None

    def tearDown(self):
        self.publish.stop()
        self.dir.cleanup()

    def run_wake(self, request, follow_up=None, speak_replies="voice"):
        self.engine.settings.update(speak_replies=speak_replies)
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        handled = []

        async def on_request(text):
            handled.append(text)
            return f"Done: {text}"

        self.engine.on_request = on_request
        self.engine._loop = loop
        with patch.object(self.engine, "_capture", return_value=np.zeros(10, np.float32) if follow_up else None), \
             patch.object(self.engine, "transcribe", return_value=follow_up or ""):
            self.engine._handle_wake(request, read=lambda: np.zeros(1600, np.float32))
        loop.call_soon_threadsafe(loop.stop)
        thread.join(2)
        return handled

    def test_request_in_one_breath_is_routed_and_spoken(self):
        handled = self.run_wake("open notepad")
        self.assertEqual(handled, ["open notepad"])
        self.assertEqual(self.spoken, ["Done: open notepad"])
        stages = [p.get("stage") for e, p in self.events if e == "voice"]
        self.assertEqual(stages[:2], ["wake", "heard"])
        self.assertIn("answered", stages)

    def test_wake_alone_listens_for_the_request(self):
        self.assertEqual(self.run_wake("", follow_up="what time is it"), ["what time is it"])

    def test_silence_after_wake_does_nothing(self):
        self.assertEqual(self.run_wake("", follow_up=None), [])
        self.assertIn("no_speech", [p.get("stage") for _, p in self.events])

    def test_never_speak_setting_is_respected(self):
        self.run_wake("open notepad", speak_replies="never")
        self.assertEqual(self.spoken, [])


class VoiceSettingsTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = VoiceSettings(Path(directory) / "voice.json")
            self.assertFalse(settings.load()["wake_word"])  # always-on listening is opt-in
            with self.assertRaises(ValueError):
                settings.update(voice="nobody")
            with self.assertRaises(ValueError):
                settings.update(speak_replies="sometimes")
            self.assertEqual(settings.update(speed=9)["speed"], 1.5)


class SpeechApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.local = TestClient(app, client=("127.0.0.1", 50000))
        self.remote = TestClient(app, client=("10.0.0.5", 50000))

    def test_microphone_controls_are_local_only(self):
        for method, path in (("get", "/api/v1/speech"), ("post", "/api/v1/speech/listen"), ("post", "/api/v1/speech/stop")):
            self.assertEqual(getattr(self.remote, method)(path).status_code, 403, path)

    def test_listen_explains_missing_download(self):
        from app.voice.engine import voice_engine
        with patch.object(type(voice_engine), "ready", return_value=False):
            reply = self.local.post("/api/v1/speech/listen")
        self.assertEqual(reply.status_code, 409)
        self.assertIn("Download", reply.json()["detail"])

    def test_unknown_voice_rejected(self):
        self.assertEqual(self.local.put("/api/v1/speech/settings", json={"voice": "nobody"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
