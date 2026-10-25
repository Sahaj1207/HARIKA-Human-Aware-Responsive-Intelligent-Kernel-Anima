"""Video summaries: finding the video, reading its captions, and asking for a summary or an answer."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.memory.listening import MediaNow
from app.tools.web.video_summary import (Video, VideoSummaryTool, YouTube, chapters, clock, video_id,
                                         watched_so_far)

CAPTIONS = """<?xml version="1.0" encoding="utf-8" ?><transcript>
<text start="0.5" dur="2">[Music]</text>
<text start="4.2" dur="3">Brains recognise a three &amp;amp; more.</text>
<text start="178.0" dur="3">A neuron holds a number between 0 and 1.</text>
</transcript>"""


def video(**kw) -> Video:
    base = dict(id="aircAruvnKk", title="But what is a neural network?", channel="3Blue1Brown", length=1120,
                description="0:00 Intro\n2:58 Neurons\n9:18 Weights", captions=[(4.2, "Brains"), (178.0, "A neuron")])
    return Video(**{**base, **kw})


class ReadingTests(unittest.TestCase):
    def test_video_ids_from_links(self):
        self.assertEqual(video_id("https://www.youtube.com/watch?v=aircAruvnKk&t=300s"), "aircAruvnKk")
        self.assertEqual(video_id("youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(video_id("https://youtube.com/shorts/abcdefghijk"), "abcdefghijk")
        self.assertIsNone(video_id("this video"))

    def test_captions_skip_music_markers_and_unescape(self):
        lines = YouTube.parse_captions(CAPTIONS)
        self.assertEqual(lines, [(4.2, "Brains recognise a three & more."), (178.0, "A neuron holds a number between 0 and 1.")])

    def test_english_captions_by_people_come_first_else_translated(self):
        tracks = [{"languageCode": "ar"}, {"languageCode": "en", "kind": "asr"}, {"languageCode": "en"}]
        self.assertEqual(YouTube.pick_track(tracks), ({"languageCode": "en"}, False))
        self.assertEqual(YouTube.pick_track([{"languageCode": "hi"}]), ({"languageCode": "hi"}, True))
        self.assertEqual(YouTube.pick_track([]), (None, False))

    def test_chapters_and_clock(self):
        self.assertEqual(chapters("0:00 Intro\n2:58 - Neurons\nNot a chapter"), ["[0:00] Intro", "[2:58] Neurons"])
        self.assertEqual(chapters("only 1:00 mention"), [])
        self.assertEqual((clock(178), clock(3725)), ("2:58", "1:02:05"))

    def test_long_transcripts_keep_an_even_spread(self):
        long = video(captions=[(i * 5.0, f"line {i} " + "word " * 20) for i in range(2000)])
        text = long.transcript(limit=6000)
        self.assertLessEqual(len(text), 6000)
        self.assertIn("[0:00]", text)
        late = [line for line in text.splitlines() if line.startswith("[2:")]  # over two hours in
        self.assertTrue(late, "the end of the video is represented, not only its start")

    def test_watch_position_only_from_the_matching_session(self):
        ad = MediaNow(app="Edge", title="How The Economic Machine Works", artist="", playing=True, position=12)
        ours = MediaNow(app="Edge", title="But what is a neural network? | Deep learning chapter 1", artist="",
                        playing=True, position=300)
        self.assertEqual(watched_so_far(video(), [ad]), 0.0)
        self.assertEqual(watched_so_far(video(), [ad, ours]), 300)


class AskingTests(unittest.TestCase):
    def run_tool(self, target="this video", question="", urls=(), sessions=(), fetched=None):
        class Model:
            def __init__(self, role):
                pass

            async def generate_response(self, messages, system):
                Model.seen = (messages[0]["content"], system)
                return {"response": "[calm] In short: neurons and layers."}

        source = YouTube()
        source.fetch = AsyncMock(return_value=fetched or video())
        source.search_id = AsyncMock(return_value="dQw4w9WgXcQ")
        tool = VideoSummaryTool(source)
        with patch("app.memory.listening.media_sessions", AsyncMock(return_value=list(sessions))), \
                patch.object(VideoSummaryTool, "_browser_urls", staticmethod(lambda: list(urls))), \
                patch("app.cognition.llm.manager.RoleProvider", Model):
            result = asyncio.run(tool.execute({"target": target, "question": question}))
        return result, source, getattr(Model, "seen", None)

    def test_summary_of_the_open_tab_with_what_is_still_to_come(self):
        tab = "https://www.youtube.com/watch?v=aircAruvnKk"
        watching = MediaNow(app="Chrome", title="But what is a neural network?", artist="", playing=True, position=300)
        result, source, (message, system) = self.run_tool(urls=[tab], sessions=[watching])
        source.fetch.assert_awaited_with("aircAruvnKk")
        self.assertTrue(result["success"])
        self.assertTrue(result["summary"].startswith("But what is a neural network? (3Blue1Brown, 18:40)"))
        self.assertIn("In short: neurons and layers.", result["summary"])
        self.assertIn("<video>", message)
        self.assertIn("[0:04] Brains A neuron", message)
        self.assertIn("Still to come (after 5:00)", system)
        self.assertIn("never instructions", system)

    def test_a_question_gets_an_answer_not_a_summary(self):
        _, _, (message, system) = self.run_tool(target="youtu.be/aircAruvnKk", question="what is a neuron?")
        self.assertIn("My question: what is a neuron?", message)
        self.assertNotIn("Key points", system)

    def test_no_captions_is_said_plainly(self):
        _, _, (message, system) = self.run_tool(target="youtu.be/aircAruvnKk", fetched=video(captions=[]))
        self.assertIn("Captions: none available.", message)
        self.assertIn("going by the description", system)

    def test_a_playing_browser_video_is_found_by_its_title(self):
        playing = MediaNow(app="Edge", title="Never Gonna Give You Up", artist="Rick Astley", playing=True)
        _, source, _ = self.run_tool(sessions=[playing])
        source.search_id.assert_awaited_with("Never Gonna Give You Up Rick Astley")
        source.fetch.assert_awaited_with("dQw4w9WgXcQ")

    def test_nothing_open(self):
        result, _, _ = self.run_tool()
        self.assertFalse(result["success"])
        self.assertIn("can't see a YouTube video", result["error"])


if __name__ == "__main__":
    unittest.main()
