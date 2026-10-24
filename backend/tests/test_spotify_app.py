"""Spotify through the app (no developer API): matching, the player bar, routing, and honest reports."""
import asyncio
import unittest
from unittest.mock import patch

from app.tools.web import spotify_app
from app.tools.web.spotify_app import SpotifyAppError, _best_result, _Button, _player_like_button, is_playing, split_title


def run(coro):
    return asyncio.run(coro)


def buttons(*names):
    return [_Button(None, name) for name in names]


class ReadingTests(unittest.TestCase):
    def test_titles(self):
        self.assertTrue(is_playing("Imagine Dragons - Believer"))
        self.assertFalse(is_playing("Spotify Premium"))
        self.assertEqual(split_title("Pritam - Kesariya (From \"Brahmastra\")"), ('Kesariya (From "Brahmastra")', "Pritam"))

    def test_best_search_result(self):
        found = buttons("Play Daily Mix 2", "Play Kesariya Rangu", 'Play Kesariya (From "Brahmastra")', "Playing on OnePlus Nord 5")
        self.assertEqual(_best_result(found, "Play ", "kesariya brahmastra").Name, 'Play Kesariya (From "Brahmastra")')
        self.assertEqual(_best_result(found, "Play ", "kesariya").Name, "Play Kesariya Rangu")  # first of equals
        self.assertIsNone(_best_result(found, "Play ", "believer"))
        menus = buttons("More options for Ruaan", "More options for Believer by Imagine Dragons")
        self.assertEqual(_best_result(menus, "More options for ", "believer").Name, "More options for Believer by Imagine Dragons")

    def test_player_bar_like_button(self):
        bar = buttons("Now playing view", "Hide song", "Add to Liked Songs", "Shuffle", "Previous", "Play", "Next")
        self.assertEqual(_player_like_button(bar).Name, "Add to Liked Songs")
        liked = buttons("Add to playlist", "Enable Shuffle for Evolve", "Previous", "Pause")
        self.assertEqual(_player_like_button(liked).Name, "Add to playlist")
        self.assertIsNone(_player_like_button(buttons("Play", "Add to Liked Songs")))


class PlayTests(unittest.TestCase):
    def setUp(self):
        self.installed = patch.object(spotify_app, "installed", return_value=True)
        self.installed.start()

    def tearDown(self):
        self.installed.stop()

    def test_play_confirmed_by_the_title(self):
        with patch.object(spotify_app, "play_blocking", return_value=("Imagine Dragons - Believer", "OnePlus Nord 5", "Believer")):
            self.assertEqual(run(spotify_app.play("believer")),
                             (True, "Playing Believer by Imagine Dragons on Spotify, on your OnePlus Nord 5."))

    def test_never_claims_what_did_not_start(self):
        with patch.object(spotify_app, "play_blocking", return_value=("", "", "Believer")):
            played, message = run(spotify_app.play("believer"))
        self.assertFalse(played)
        self.assertIn("didn't start", message)
        with patch.object(spotify_app, "play_blocking", side_effect=SpotifyAppError("I couldn't find zzz on Spotify")):
            self.assertEqual(run(spotify_app.play("zzz")), (False, "I couldn't find zzz on Spotify"))

    def test_liked_songs(self):
        with patch.object(spotify_app, "play_liked_blocking", return_value=("Pritam - Kesariya", "")):
            self.assertEqual(run(spotify_app.play_liked()), (True, "Playing your liked songs on Spotify."))


class RoutingTests(unittest.TestCase):
    """Not connected through Spotify's API: every Spotify request goes through the app."""

    def setUp(self):
        self.patches = [
            patch("app.integrations.spotify.spotify_account.status", return_value={"connected": False}),
            patch.object(spotify_app, "installed", return_value=True),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def tool(self, **args):
        from app.tools.web.spotify_tool import spotify_tool
        return run(spotify_tool.execute(args))

    def test_each_request_uses_the_app(self):
        with patch.object(spotify_app, "spotify_window", return_value=(1, "Imagine Dragons - Believer")):
            self.assertEqual(self.tool(operation="now_playing")["summary"], "Playing Believer by Imagine Dragons.")
        with patch.object(spotify_app, "like_current_blocking", return_value="Saved Believer by Imagine Dragons to your liked songs."):
            self.assertTrue(self.tool(operation="like_song")["success"])
        queued = self.tool(operation="queue_song", target="levitating")
        self.assertFalse(queued["success"])
        self.assertIn("To queue songs, connect Spotify in Settings > Accounts", queued["error"])
        added = self.tool(operation="add_to_playlist_spotify", target="gym")
        self.assertIn("To add songs to your playlists, connect Spotify", added["error"])

    def test_liked_songs_and_playlists(self):
        async def liked():
            return True, "Playing your liked songs on Spotify."

        async def play(query, kind):
            return True, f"Playing {query}."
        with patch.object(spotify_app, "play_liked", liked), patch.object(spotify_app, "play", play):
            self.assertEqual(self.tool(operation="play_library", target="liked songs")["summary"], "Playing your liked songs on Spotify.")
            self.assertEqual(self.tool(operation="play_library", target="workout")["summary"], "Playing workout.")

    def test_nothing_playing(self):
        with patch.object(spotify_app, "spotify_window", return_value=(1, "Spotify Premium")):
            self.assertEqual(self.tool(operation="now_playing")["summary"], "Nothing is playing on Spotify right now.")

    def test_play_on_spotify_uses_the_app(self):
        from app.tools.web.media_playback import media_playback_tool

        async def play(query, kind):
            return True, "Playing Believer by Imagine Dragons on Spotify."
        with patch.object(spotify_app, "play", play):
            result = run(media_playback_tool.execute({"target": "believer", "platform": "spotify"}))
        self.assertEqual(result["summary"], "Playing Believer by Imagine Dragons on Spotify.")


if __name__ == "__main__":
    unittest.main()
