"""Music taste: learning what's played on this computer, and picking music that fits."""
import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.memory.listening import ListeningLog, MediaNow, app_name
from app.tools.web.music_taste import MusicTasteTool

EVENING = datetime(2026, 10, 24, 19, 30)


def log() -> ListeningLog:
    folder = Path(tempfile.mkdtemp(prefix="harika-listen-"))
    return ListeningLog(folder / "listening.json", folder / "settings.json")


def song(title, artist, app="Spotify", playing=True) -> MediaNow:
    return MediaNow(app=app, title=title, artist=artist, playing=playing)


class ListeningTests(unittest.TestCase):
    def test_app_names_are_readable(self):
        self.assertEqual(app_name("Spotify.exe"), "Spotify")
        self.assertEqual(app_name("MSEdge"), "Edge")
        self.assertEqual(app_name("Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic"), "Media Player")

    def test_a_track_counts_once_heard_for_30_seconds(self):
        history = log()
        history.observe([song("Kesariya", "Arijit Singh")], 20)
        history.observe([song("Kesariya", "Arijit Singh")], 20)
        history.observe([song("Believer", "Imagine Dragons")], 20)  # Kesariya ended after 40 s
        history.observe([], 20)  # Believer stopped after 20 s: a skip, not counted
        plays = history.plays()
        self.assertEqual([(p["title"], p["artist"], p["app"], p["seconds"]) for p in plays],
                         [("Kesariya", "Arijit Singh", "Spotify", 40)])

    def test_paused_media_is_not_heard(self):
        history = log()
        history.observe([song("Kesariya", "Arijit Singh", playing=False)], 60)
        history.observe([], 20)
        self.assertEqual(history.plays(), [])

    def test_nothing_is_kept_while_learning_is_off(self):
        history = log()
        history.set_learning(False)
        history.observe([song("Kesariya", "Arijit Singh")], 60)
        history.observe([], 20)
        self.assertEqual(history.plays(), [])
        self.assertFalse(history.learning())

    def test_profile_by_artist_time_of_day_and_app(self):
        history = log()
        history.record("Kesariya", "Arijit Singh", "Spotify", 300, EVENING - timedelta(days=1))
        history.record("Apna Bana Le", "Arijit Singh", "Spotify", 200, EVENING - timedelta(days=2))
        history.record("Lofi beats", "Lofi Girl", "Edge", 900, EVENING.replace(hour=10) - timedelta(days=1))
        profile = history.profile(EVENING)
        self.assertEqual(profile["top_artists"], ["Lofi Girl", "Arijit Singh"])
        self.assertEqual(profile["by_time_of_day"]["evening"], ["Arijit Singh"])
        self.assertEqual(profile["by_time_of_day"]["morning"], ["Lofi Girl"])
        self.assertEqual(profile["apps"], ["Edge", "Spotify"])
        self.assertEqual(profile["now_part"], "evening")
        self.assertIn("In the evening: Arijit Singh.", ListeningLog.describe(profile))

    def test_forget(self):
        history = log()
        history.record("Kesariya", "Arijit Singh", "Spotify", 300, EVENING)
        history.forget()
        self.assertEqual(history.plays(), [])


class PickingTests(unittest.TestCase):
    def setUp(self):
        self.history = log()
        self.history.record("Kesariya", "Arijit Singh", "Spotify", 600, datetime.now() - timedelta(hours=1))
        self.tool = MusicTasteTool(self.history)

    def play(self, model_reply, **args):
        class Model:
            def __init__(self, role):
                pass

            async def generate_response(self, messages, system, json_mode=False):
                Model.system = system
                return {"response": model_reply}

        player = AsyncMock(return_value={"success": True, "verified": True, "summary": "Playing it on Spotify."})
        with patch("app.cognition.llm.manager.RoleProvider", Model), \
                patch("app.tools.web.media_playback.media_playback_tool.execute", player):
            result = asyncio.run(self.tool.execute({"operation": "play_for_me", **args}))
        return result, player.call_args.args[0], Model.system

    def test_the_model_picks_from_their_taste_and_the_player_plays_it(self):
        result, played, system = self.play('{"query": "Arijit Singh romantic mix", "why": "You love Arijit in the evenings."}',
                                           target="anything")
        self.assertIn("Arijit Singh", system)  # the profile is what the model chooses from
        self.assertEqual(played, {"target": "Arijit Singh romantic mix", "platform": "spotify"})
        self.assertEqual(result["summary"], "You love Arijit in the evenings. Playing it on Spotify.")

    def test_a_platform_they_name_wins(self):
        _, played, _ = self.play('{"query": "lofi coding mix", "why": ""}', target="coding", platform="youtube")
        self.assertEqual(played["platform"], "youtube")

    def test_an_unusable_pick_falls_back_to_their_top_artist(self):
        _, played, _ = self.play('{"query": "https://evil.example/x", "why": "trust me"}', target="workout")
        self.assertEqual(played["target"], "Arijit Singh workout mix")

    def test_taste_summary(self):
        result = asyncio.run(self.tool.execute({"operation": "music_taste", "target": "me"}))
        self.assertTrue(result["summary"].startswith("Lately you play a lot of Arijit Singh"))

    def test_taste_summary_before_hearing_anything(self):
        result = asyncio.run(MusicTasteTool(log()).execute({"operation": "music_taste", "target": "me"}))
        self.assertIn("haven't heard you play much yet", result["summary"])


class SettingsTests(unittest.TestCase):
    def test_memory_settings_show_and_control_listening(self):
        from app.main import app
        history = log()
        history.record("Kesariya", "Arijit Singh", "Spotify", 600, datetime.now())
        client = TestClient(app, client=("127.0.0.1", 50000))
        with patch("app.memory.listening.listening_log", history):
            shown = client.get("/api/v1/memory/overview").json()["listening"]
            self.assertEqual((shown["learn"], shown["plays"], shown["top_artists"]), (True, 1, ["Arijit Singh"]))
            off = client.put("/api/v1/memory/settings", json={"learn_listening": False}).json()["listening"]
            self.assertFalse(off["learn"])
            gone = client.post("/api/v1/memory/forget-listening").json()["listening"]
            self.assertEqual(gone["plays"], 0)


if __name__ == "__main__":
    unittest.main()
