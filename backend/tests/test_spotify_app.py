"""Playing on Spotify through the app (no developer API): finding the page, confirming, reporting honestly."""
import asyncio
import unittest
from unittest.mock import patch

from app.tools.web import spotify_app
from app.tools.web.spotify_app import Found, choose, is_playing, parse_title

RESULTS = [
    {"url": "https://www.youtube.com/watch?v=abc", "title": "Believer (Official Video) - YouTube"},
    {"url": "https://open.spotify.com/album/3d74p8E8jFhgKogypxpZAd", "title": "Believer - Single by Imagine Dragons | Spotify"},
    {"url": "https://open.spotify.com/track/0pqnGHJpmpxLKifKRmU6WP", "title": "Believer - song and lyrics by Imagine Dragons | Spotify"},
    {"url": "https://open.spotify.com/artist/53XhwfbYqKCa1cC15pYq2q", "title": "Imagine Dragons | Spotify"},
]


def run(coro):
    return asyncio.run(coro)


class FindingTests(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(parse_title("Believer - song and lyrics by Imagine Dragons | Spotify"), ("Believer", "Imagine Dragons"))
        self.assertEqual(parse_title("Evolve - Album by Imagine Dragons | Spotify"), ("Evolve", "Imagine Dragons"))
        self.assertEqual(parse_title("lofi beats | Spotify Playlist"), ("lofi beats", ""))

    def test_choose_the_right_kind_and_name(self):
        song = choose(RESULTS, "believer imagine dragons", "track")
        self.assertEqual((song.kind, song.uri), ("track", "spotify:track:0pqnGHJpmpxLKifKRmU6WP"))
        self.assertEqual(choose(RESULTS, "imagine dragons", "artist").kind, "artist")
        self.assertIsNone(choose(RESULTS, "kesariya", "track"))  # nothing about it: no guess
        self.assertIsNone(choose([], "anything", "track"))

    def test_playing_titles(self):
        self.assertTrue(is_playing("Imagine Dragons - Believer"))
        self.assertFalse(is_playing("Spotify Premium"))
        self.assertFalse(is_playing("Spotify"))


class PlayTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(spotify_app, "installed", return_value=True)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def found(self, value):
        async def find(*args, **kwargs):
            return value
        return patch.object(spotify_app, "find", find)

    def test_web_route_confirmed_by_the_title(self):
        believer = Found("track", "spotify:track:x", "Believer", "Imagine Dragons")
        with self.found(believer), patch.object(spotify_app, "_open_and_play",
                                                return_value=("Imagine Dragons - Believer", "Playing on OnePlus Nord 5")):
            played, message = run(spotify_app.play("believer"))
        self.assertTrue(played)
        self.assertEqual(message, "Playing Believer by Imagine Dragons on Spotify, on your OnePlus Nord 5.")

    def test_never_claims_what_did_not_start(self):
        believer = Found("track", "spotify:track:x", "Believer", "Imagine Dragons")
        with self.found(believer), patch.object(spotify_app, "_open_and_play", return_value=("", "")):
            played, message = run(spotify_app.play("believer"))
        self.assertFalse(played)
        self.assertIn("couldn't start it. Press play there", message)

    def test_a_different_song_is_reported_as_such(self):
        believer = Found("track", "spotify:track:x", "Believer", "Imagine Dragons")
        with self.found(believer), patch.object(spotify_app, "_open_and_play", return_value=("Imagine Dragons - Thunder", "")):
            played, message = run(spotify_app.play("believer"))
        self.assertTrue(played)
        self.assertEqual(message, "Spotify is playing Thunder, not exactly Believer by Imagine Dragons.")

    def test_falls_back_to_spotifys_own_search(self):
        with self.found(None), patch.object(spotify_app, "_search_in_app",
                                            return_value=('Pritam - Kesariya (From "Brahmastra")', "", 'Kesariya (From "Brahmastra")')):
            played, message = run(spotify_app.play("kesariya"))
        self.assertTrue(played)
        self.assertEqual(message, 'Playing Kesariya (From "Brahmastra") by Pritam on Spotify.')
        with self.found(None), patch.object(spotify_app, "_search_in_app", return_value=("", "", "")):
            self.assertEqual(run(spotify_app.play("zzz")), (False, "I couldn't find zzz on Spotify"))

    def test_media_tool_uses_the_app_when_not_connected(self):
        from app.tools.web.media_playback import media_playback_tool

        async def play(query, kind):
            return True, "Playing Believer by Imagine Dragons on Spotify."
        with patch("app.integrations.spotify.spotify_account.status", return_value={"connected": False}), \
                patch.object(spotify_app, "play", play):
            result = run(media_playback_tool.execute({"target": "believer", "platform": "spotify"}))
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"], "Playing Believer by Imagine Dragons on Spotify.")


if __name__ == "__main__":
    unittest.main()
