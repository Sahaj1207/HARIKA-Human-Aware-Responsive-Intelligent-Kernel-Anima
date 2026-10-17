"""Tone of replies and the expressive (Azure) voice. No network, microphone or speakers."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.presence.tone import split_tone, strip_tags, tone_for
from app.voice import azure_tts
from app.voice.engine import VoiceEngine, VoiceSettings


class ToneTests(unittest.TestCase):
    def test_tags_are_removed_and_read(self):
        self.assertEqual(split_tone("[empathetic] That sounds hard."), ("That sounds hard.", "empathetic"))
        self.assertEqual(split_tone("(cheerful): Done!"), ("Done!", "cheerful"))
        self.assertEqual(split_tone("[Note] keep this"), ("[Note] keep this", None))  # unknown tags stay
        self.assertEqual(strip_tags("[warm] Hi.\n\n[cheerful] Added milk."), ("Hi.\n\nAdded milk.", "warm"))

    def test_tone_from_outcomes(self):
        ok = {"result": {"success": True, "summary": "Added milk."}}
        failed = {"result": {"success": False, "error": "no"}}
        birthday = {"result": {"success": True, "tone": "excited"}}
        self.assertEqual(tone_for([ok], None), "warm")
        self.assertEqual(tone_for([failed], None), "apologetic")
        self.assertEqual(tone_for([birthday], None), "excited")
        self.assertEqual(tone_for([ok], "playful"), "playful")
        self.assertEqual(tone_for([ok], "playful", asking=True), "neutral")  # approvals are always plain

    def test_social_replies_carry_a_tone(self):
        from app.presence.communication.social import social_formatter
        text, tone = split_tone(social_formatter.format_social_response(raw_message="I'm so stressed"))
        self.assertEqual(tone, "empathetic")
        self.assertNotIn("[", text)


class AzureSsmlTests(unittest.TestCase):
    def test_style_follows_tone_and_voice(self):
        self.assertEqual(azure_tts.style_for("en-US-AriaNeural", "empathetic")[0], "empathetic")
        self.assertEqual(azure_tts.style_for("en-GB-SoniaNeural", "excited")[0], "cheerful")  # nearest it supports
        self.assertIsNone(azure_tts.style_for("en-US-AriaNeural", "serious")[0])

    def test_text_is_escaped_never_markup(self):
        xml = azure_tts.ssml('Tom & Jerry <break time="5s"/> "hi"', "en-US-AriaNeural", "cheerful")
        self.assertIn("Tom &amp; Jerry &lt;break", xml)
        self.assertIn('<mstts:express-as style="cheerful"', xml)
        self.assertNotIn('<break time="5s"/>', xml)


class AzureVoiceFallbackTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.engine = VoiceEngine()
        self.engine.settings = VoiceSettings(Path(self.folder.name) / "voice.json")
        self.engine.settings.update(engine="azure", azure_region="centralindia")

    def tearDown(self):
        self.folder.cleanup()

    def test_azure_speaks_with_the_tone(self):
        audio = (np.zeros(10, dtype=np.float32), 24000)
        with patch.object(azure_tts, "has_key", return_value=True), \
             patch.object(azure_tts.azure_speech, "_failed_at", 0.0), \
             patch.object(azure_tts.azure_speech, "synthesize", return_value=audio) as azure:
            self.assertIs(self.engine.synthesize("Happy birthday!", tone="excited"), audio)
        self.assertEqual(azure.call_args.args[3], "excited")

    def test_offline_voice_takes_over_when_azure_fails(self):
        class Piper:
            def generate(self, text, sid, speed):
                self.speed = speed
                return type("Audio", (), {"samples": [0.0], "sample_rate": 22050})()
        piper = Piper()
        with patch.object(azure_tts, "has_key", return_value=True), \
             patch.object(azure_tts.azure_speech, "_failed_at", 0.0), \
             patch.object(azure_tts.azure_speech, "synthesize", side_effect=OSError("offline")), \
             patch.object(VoiceEngine, "_load_tts", return_value=piper):
            _, rate = self.engine.synthesize("I'm sorry.", tone="empathetic")
        self.assertEqual(rate, 22050)
        self.assertAlmostEqual(piper.speed, 0.93)  # gentler pace carries the mood offline

    def test_can_speak_with_azure_alone(self):
        with patch.object(azure_tts, "has_key", return_value=True), patch.object(VoiceEngine, "ready", return_value=False):
            self.assertTrue(self.engine.can_speak())


if __name__ == "__main__":
    unittest.main()
