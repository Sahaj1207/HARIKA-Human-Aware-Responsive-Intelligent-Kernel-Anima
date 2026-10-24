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
        self.engine.speak = lambda text, voice_id=None, tone=None: self.spoken.append(text)
        self.engine._chime = lambda: None

    def tearDown(self):
        self.publish.stop()
        self.dir.cleanup()

    def run_wake(self, request, follow_up=None, speak_replies="voice", heard=None, keep_listening=False):
        """heard: what each microphone capture transcribes to, in order ("" = silence)."""
        self.engine.settings.update(speak_replies=speak_replies, follow_up=keep_listening)
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        handled = []

        async def on_request(text):
            handled.append(text)
            return f"Done: {text}"

        self.engine.on_request = on_request
        self.engine._loop = loop
        if heard is not None:
            captures = patch.object(self.engine, "_capture", side_effect=[np.zeros(10, np.float32) if h else None for h in heard])
            transcripts = patch.object(self.engine, "transcribe", side_effect=[h for h in heard if h])
        else:
            captures = patch.object(self.engine, "_capture", return_value=np.zeros(10, np.float32) if follow_up else None)
            transcripts = patch.object(self.engine, "transcribe", return_value=follow_up or "")
        with captures, transcripts:
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

    def test_follow_ups_continue_until_a_pause(self):
        handled = self.run_wake("what's the weather", heard=["and tomorrow?", "thanks", ""], keep_listening=True)
        self.assertEqual(handled, ["what's the weather", "and tomorrow?", "thanks"])
        self.assertEqual(len(self.spoken), 3)

    def test_without_follow_ups_one_request_ends_it(self):
        self.assertEqual(self.run_wake("what's the weather", heard=["and tomorrow?"]), ["what's the weather"])

    def test_talking_over_her_becomes_the_next_request(self):
        def speak(text, voice_id=None, tone=None):
            self.spoken.append(text)
            if len(self.spoken) == 1:
                self.engine._barged = "actually open chrome"  # what _listen_while_speaking records
        self.engine.speak = speak
        handled = self.run_wake("tell me a long story", heard=[])
        self.assertEqual(handled, ["tell me a long story", "actually open chrome"])

    def push_to_talk_reply(self, heard, follow_up=True, stopped=False):
        self.engine.settings.update(follow_up=follow_up)

        def speak(text, voice_id=None, tone=None):
            self.spoken.append(text)
            if stopped:
                self.engine._interrupt.set()
        self.engine.speak = speak
        self.engine._interrupt.clear()
        with patch.object(self.engine, "ready", return_value=True), \
             patch.object(self.engine, "listen_once", return_value=heard) as listen:
            self.engine.speak_and_follow_up("It's sunny.", "cheerful", "main")
        return listen, [p for e, p in self.events if e == "voice_follow_up"]

    def test_push_to_talk_reply_listens_for_a_follow_up(self):
        listen, events = self.push_to_talk_reply("and tomorrow?")
        self.assertEqual(self.spoken, ["It's sunny."])
        self.assertEqual([(e["phase"], e.get("text")) for e in events], [("listening", None), ("heard", "and tomorrow?")])
        self.assertTrue(all(e["conversation"] == "main" for e in events))

    def test_no_follow_up_when_stopped_or_switched_off(self):
        listen, events = self.push_to_talk_reply("and tomorrow?", stopped=True)
        listen.assert_not_called()
        self.assertEqual(events, [])
        listen, events = self.push_to_talk_reply("and tomorrow?", follow_up=False)
        listen.assert_not_called()

    def test_never_speak_setting_is_respected(self):
        self.run_wake("open notepad", speak_replies="never")
        self.assertEqual(self.spoken, [])


class GlowLevelTests(unittest.TestCase):
    def test_loudness_scale(self):
        from app.voice.engine import loudness
        self.assertEqual(loudness(np.zeros(1600, np.float32)), 0.0)
        quiet, speech = loudness(np.full(1600, 0.002, np.float32)), loudness(np.full(1600, 0.05, np.float32))
        self.assertLess(quiet, 0.2)
        self.assertGreater(speech, 0.5)
        self.assertEqual(loudness(np.full(1600, 0.9, np.float32)), 1.0)

    def test_speaking_levels_follow_the_clip(self):
        engine = VoiceEngine(VoiceSettings(Path(tempfile.mkdtemp(prefix="harika-voice-")) / "voice.json"))
        sent = []
        with patch.object(VoiceEngine, "_publish", side_effect=lambda event, **p: sent.append((event, p))), \
                patch("app.voice.engine.time.sleep"):
            clip = np.concatenate([np.zeros(2400, np.float32), np.full(2400, 0.1, np.float32)])
            engine._publish_speaking_levels(clip, 24000, step=0.05)
        levels = [p["level"] for e, p in sent if e == "voice_level" and p["kind"] == "speaking"]
        self.assertEqual(len(levels), 4)  # 0.2 s of audio in 0.05 s steps
        self.assertEqual(levels[:2], [0.0, 0.0])
        self.assertGreater(levels[-1], 0.5)


class OwnVoiceTests(unittest.TestCase):
    def test_echo_of_her_reply_is_ignored(self):
        from app.voice.engine import is_own_voice
        saying = "It's 30 degrees and mostly clear in Hyderabad today."
        self.assertTrue(is_own_voice("mostly clear in hyderabad", saying))
        self.assertTrue(is_own_voice("uh", saying))
        self.assertFalse(is_own_voice("wait stop open chrome", saying))
        self.assertFalse(is_own_voice("hey harika what time is it", saying))


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
