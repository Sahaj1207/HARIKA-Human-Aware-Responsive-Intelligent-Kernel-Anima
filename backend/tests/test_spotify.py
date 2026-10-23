"""Spotify: sign-in setup, playback requests and errors, against a fake Spotify (no network)."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.integrations.spotify import SpotifyAccount, SpotifyError
from app.tools.web.spotify_tool import SpotifyPlayer, SpotifyTool

TRACK = {"id": "t1", "uri": "spotify:track:t1", "name": "Believer", "artists": [{"name": "Imagine Dragons"}],
         "album": {"name": "Evolve"}}


class FakeSpotify:
    """Answers like Spotify's Web API and records every call."""

    def __init__(self, devices=None, playing=True):
        self.calls = []
        self.devices = [{"id": "pc", "type": "Computer", "is_active": False}] if devices is None else devices
        self.playing = playing

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/me/player/devices":
            return {"devices": self.devices}
        if path == "/search":
            kind = kwargs["params"]["type"]
            items = {"track": [TRACK], "artist": [{"name": "Arijit Singh", "uri": "spotify:artist:a1"}],
                     "playlist": [{"name": "Chill Vibes", "uri": "spotify:playlist:pub"}]}.get(kind, [])
            return {f"{kind}s": {"items": items}}
        if path == "/me/tracks" and method == "GET":
            return {"items": [{"track": {"uri": f"spotify:track:{i}"}} for i in range(5)]}
        if path == "/me/playlists":
            return {"items": [{"id": "p1", "name": "Workout Mix", "uri": "spotify:playlist:p1"},
                              {"id": "p2", "name": "Road Trip", "uri": "spotify:playlist:p2"}], "next": None}
        if path == "/me/player/currently-playing":
            return {"item": TRACK, "is_playing": True} if self.playing else None
        return None

    def sent(self, method, prefix):
        return [c for c in self.calls if c[0] == method and c[1].startswith(prefix)]


def run(coro):
    return asyncio.run(coro)


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeSpotify()
        self.player = SpotifyPlayer(self.api)

    def test_play_a_song_and_an_artist(self):
        self.assertEqual(run(self.player.play_search("believer")), "Playing Believer by Imagine Dragons on Spotify.")
        self.assertEqual(self.api.sent("PUT", "/me/player/play")[-1][2]["json"], {"uris": ["spotify:track:t1"]})
        self.assertEqual(self.api.sent("PUT", "/me/player/play")[-1][1], "/me/player/play?device_id=pc")
        self.assertEqual(run(self.player.play_search("arijit", "artist")), "Playing Arijit Singh on Spotify.")
        self.assertEqual(self.api.sent("PUT", "/me/player/play")[-1][2]["json"], {"context_uri": "spotify:artist:a1"})

    def test_liked_songs_and_own_playlists(self):
        self.assertEqual(run(self.player.play_library("liked songs")), "Playing your liked songs on Spotify, shuffled.")
        self.assertEqual(len(self.api.sent("PUT", "/me/player/play")[-1][2]["json"]["uris"]), 5)
        self.assertEqual(run(self.player.play_library("workout")), "Playing your Workout Mix playlist on Spotify.")
        self.assertEqual(run(self.player.play_library("chill vibes")), "Playing Chill Vibes on Spotify.")  # public one

    def test_now_playing_like_add_and_queue(self):
        tool = SpotifyTool(self.player)
        now = run(tool.execute({"operation": "now_playing"}))["summary"]
        self.assertEqual(now, "Playing Believer by Imagine Dragons, from Evolve.")
        self.assertEqual(run(self.player.like_current()), "Saved Believer by Imagine Dragons to your liked songs.")
        self.assertEqual(self.api.sent("PUT", "/me/tracks")[-1][2]["params"], {"ids": "t1"})
        self.assertEqual(run(self.player.add_current_to("road trip")), "Added Believer by Imagine Dragons to Road Trip.")
        self.assertEqual(self.api.sent("POST", "/playlists/p2/tracks")[-1][2]["json"], {"uris": ["spotify:track:t1"]})
        self.assertEqual(run(self.player.queue("believer")), "Believer by Imagine Dragons is up next.")

    def test_nothing_playing_and_no_device(self):
        quiet = SpotifyPlayer(FakeSpotify(playing=False))
        self.assertEqual(run(SpotifyTool(quiet).execute({"operation": "now_playing"}))["summary"],
                         "Nothing is playing on Spotify right now.")
        self.assertFalse(run(SpotifyTool(quiet).execute({"operation": "like_song"}))["success"])
        nowhere = SpotifyPlayer(FakeSpotify(devices=[]))
        with patch("app.tools.system.installed_apps.installed_app_index.find", return_value=None):
            result = run(SpotifyTool(nowhere).execute({"operation": "play_library", "target": "liked songs"}))
        self.assertIn("Open Spotify on your phone or computer first", result["error"])

    def test_errors_are_explained(self):
        class Refusing(FakeSpotify):
            async def request(self, method, path, **kwargs):
                if method == "PUT":
                    raise SpotifyError("Spotify only lets apps control playback on Premium accounts")
                return await super().request(method, path, **kwargs)
        result = run(SpotifyTool(SpotifyPlayer(Refusing())).execute({"operation": "play_library", "target": "liked songs"}))
        self.assertIn("Premium", result["error"])


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.account = SpotifyAccount(Path(tempfile.mkdtemp(prefix="harika-spotify-")) / "spotify.json")
        self.secret = patch("app.integrations.spotify.secrets")
        self.secret.start()

    def tearDown(self):
        self.secret.stop()

    def test_client_id_is_checked(self):
        with self.assertRaises(ValueError):
            self.account.set_client("not-an-id")
        with patch("app.integrations.spotify.bundled_client_id", return_value=""):
            self.account.set_client("0123456789abcdef0123456789abcdef")
            self.assertEqual(self.account.client_id(), "0123456789abcdef0123456789abcdef")

    def test_sign_in_uses_pkce_without_a_secret(self):
        self.account.set_client("0123456789abcdef0123456789abcdef")
        url = urlparse(self.account.start_sign_in("http://127.0.0.1:47801/api/v1/accounts/spotify/callback"))
        query = parse_qs(url.query)
        self.assertEqual(url.netloc, "accounts.spotify.com")
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertIn("user-modify-playback-state", query["scope"][0])
        self.assertNotIn("client_secret", query)
        with self.assertRaisesRegex(ValueError, "expired"):
            run(self.account.finish_sign_in("code", "wrong-state"))


class MediaToolTests(unittest.TestCase):
    def test_play_on_spotify_uses_the_api_when_connected(self):
        from app.tools.web.media_playback import media_playback_tool
        api = FakeSpotify()
        with patch("app.integrations.spotify.spotify_account.status", return_value={"connected": True}), \
                patch("app.tools.web.spotify_tool.spotify_player", SpotifyPlayer(api)):
            result = run(media_playback_tool.execute({"target": "believer", "platform": "spotify"}))
        self.assertEqual(result["summary"], "Playing Believer by Imagine Dragons on Spotify.")


if __name__ == "__main__":
    unittest.main()
