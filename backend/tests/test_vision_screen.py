"""Looking at the screen: PNG encoding, images for each AI service, and the look path. All simulated."""
import asyncio
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import numpy as np

from app.cognition.llm.providers import AnthropicProvider, GeminiProvider, OpenAICompatibleProvider
from app.core.privacy import PrivacySettings
from app.tools.system import screen_reader
from app.tools.system.screen_assist import ScreenAssistTool
from app.tools.system.screen_reader import WindowInfo, WindowText
from app.vision import screen

PNG = b"\x89PNG-fake"
WINDOW = WindowInfo(hwnd=7, pid=8, title="Sales Q3 - Excel", process="excel.exe")


class PngTests(unittest.TestCase):
    def test_png_is_valid(self):
        pixels = np.zeros((2, 3, 3), dtype=np.uint8)
        pixels[0, 0] = [255, 0, 0]
        data = screen.png(pixels)
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (3, 2))
        idat_len = struct.unpack(">I", data[33:37])[0]
        raw = zlib.decompress(data[41:41 + idat_len])
        self.assertEqual(raw[:4], b"\x00\xff\x00\x00")  # filter byte + first red pixel

    def test_shrink(self):
        self.assertEqual(screen.shrink(np.zeros((1000, 3200, 3), dtype=np.uint8)).shape[1], 1600)
        self.assertEqual(screen.shrink(np.zeros((10, 800, 3), dtype=np.uint8)).shape[1], 800)


class ImagePayloadTests(unittest.TestCase):
    """Each service gets the picture in its own format."""

    def sent_body(self, provider):
        bodies = []

        async def fake_post(self_client, url, json=None, headers=None, **kwargs):
            bodies.append(json)
            reply = {"choices": [{"message": {"content": "ok"}}], "content": [{"type": "text", "text": "ok"}],
                     "candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
            return httpx.Response(200, json=reply, request=httpx.Request("POST", url))

        with patch.object(httpx.AsyncClient, "post", fake_post):
            result = asyncio.run(provider.generate_response([{"role": "user", "content": "What is this?", "images": [PNG]}], "sys"))
        self.assertEqual(result["response"], "ok")
        return bodies[0]

    def test_openai_compatible(self):
        body = self.sent_body(OpenAICompatibleProvider("m", "k", "https://api.groq.com/openai/v1", "Groq"))
        parts = body["messages"][1]["content"]
        self.assertEqual(parts[0], {"type": "text", "text": "What is this?"})
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_gemini(self):
        body = self.sent_body(GeminiProvider("gemini-2.5-flash", "k", "https://generativelanguage.googleapis.com/v1beta"))
        self.assertEqual(body["contents"][0]["parts"][1]["inline_data"]["mime_type"], "image/png")

    def test_anthropic(self):
        body = self.sent_body(AnthropicProvider("claude", "k", "https://api.anthropic.com/v1"))
        self.assertEqual(body["messages"][0]["content"][0]["type"], "image")


class LookPathTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.privacy = PrivacySettings(Path(self.folder.name) / "privacy.json")
        self.tool = ScreenAssistTool()
        self.patches = [
            patch.object(screen_reader.foreground_tracker, "current_target", return_value=WINDOW),
            patch("app.core.privacy.privacy_settings", self.privacy),
            patch.object(screen, "capture_window", return_value=np.zeros((20, 30, 3), dtype=np.uint8)),
            patch.object(screen, "ocr", return_value=["Q3 revenue", "Up 12%"]),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.folder.cleanup()

    def run_read(self, lines, **args):
        with patch.object(screen_reader, "read_window", return_value=WindowText(WINDOW, lines, False)):
            return asyncio.run(self.tool.execute({"operation": "read", "target": "screen", **args}))

    def test_visual_question_uses_the_picture(self):
        with patch.object(screen, "ask_about_image", AsyncMock(return_value=("A bar chart: revenue up 12%.", "gemini"))) as ask:
            result = self.run_read(["Sales Q3"], look=True, question="what does this chart show?")
        self.assertEqual((result["summary"], result["seen_by"]), ("A bar chart: revenue up 12%.", "gemini"))
        self.assertIn("<window>\nSales Q3\n</window>", ask.call_args.args[2])  # on-screen words are quoted as data

    def test_app_that_hides_its_text_is_looked_at(self):
        with patch.object(screen, "ask_about_image", AsyncMock(return_value=("A login page.", "gemini"))):
            self.assertEqual(self.run_read([])["summary"], "A login page.")

    def test_without_a_vision_model_ocr_words_answer(self):
        with patch.object(screen, "ask_about_image", AsyncMock(return_value=(None, None))), \
             patch.object(ScreenAssistTool, "_ask", AsyncMock(return_value="Revenue is up 12%.")) as ask:
            result = self.run_read([], question="how is revenue?")
        self.assertEqual(result["summary"], "Revenue is up 12%.")
        self.assertIn("Up 12%", ask.call_args.args[1])

    def test_privacy_switch_stops_capturing(self):
        self.privacy.update(screen_images=False)
        with patch.object(screen, "ask_about_image", AsyncMock()) as ask:
            result = self.run_read([])
        ask.assert_not_called()
        self.assertIn("turned off in Settings > Privacy", result["error"])


if __name__ == "__main__":
    unittest.main()
