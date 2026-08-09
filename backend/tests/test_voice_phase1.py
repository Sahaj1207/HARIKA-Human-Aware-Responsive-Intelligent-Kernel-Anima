import unittest
from app.voice.schemas import VoiceState, VoiceProfile
from app.voice.manager import VoiceManager, InvalidVoiceStateTransitionError
from app.voice.base_provider import get_speaker_provider_class, get_transcriber_provider_class
from app.voice.voice_profile import voice_profile_manager


class TestVoicePhase1(unittest.TestCase):

    def setUp(self):
        self.manager = VoiceManager()

    def test_provider_registry_resolution(self):
        browser_speaker_cls = get_speaker_provider_class("browser")
        elevenlabs_speaker_cls = get_speaker_provider_class("elevenlabs")
        browser_transcriber_cls = get_transcriber_provider_class("browser")

        self.assertEqual(browser_speaker_cls.__name__, "BrowserSpeakerProvider")
        self.assertEqual(elevenlabs_speaker_cls.__name__, "ElevenLabsSpeakerProvider")
        self.assertEqual(browser_transcriber_cls.__name__, "BrowserTranscriberProvider")

    def test_voice_manager_state_machine(self):
        session = self.manager.start_session(continuous=False)
        self.assertEqual(self.manager.get_state(), VoiceState.LISTENING)

        self.manager.transition_state(VoiceState.THINKING)
        self.assertEqual(self.manager.get_state(), VoiceState.THINKING)

        self.manager.transition_state(VoiceState.SPEAKING)
        self.assertEqual(self.manager.get_state(), VoiceState.SPEAKING)

        self.manager.stop_session()
        self.assertEqual(self.manager.get_state(), VoiceState.IDLE)

    def test_invalid_state_transition(self):
        self.assertEqual(self.manager.get_state(), VoiceState.IDLE)
        # Attempting IDLE -> SPEAKING directly must fail
        with self.assertRaises(InvalidVoiceStateTransitionError):
            self.manager.transition_state(VoiceState.SPEAKING)

    def test_voice_profile_management(self):
        prof = voice_profile_manager.update_profile(speaking_rate=1.2, pitch=1.1)
        self.assertEqual(prof.speaking_rate, 1.2)
        self.assertEqual(prof.pitch, 1.1)


if __name__ == "__main__":
    unittest.main()
