import unittest
from app.core.config import settings
from app.vision.manager import VisionManager
from app.vision.preprocessing import SecurityValidationError
from app.vision.schemas import VisionResult, OCRResult


class TestVisionPhase1(unittest.TestCase):

    def setUp(self):
        self.manager = VisionManager()

    def test_provider_resolution_from_config(self):
        # Default setting should resolve to LocalVisionProvider
        provider = self.manager._get_provider()
        self.assertEqual(provider.__class__.__name__, "LocalVisionProvider")

    def test_dynamic_provider_switching(self):
        # Override to ollama, openai, gemini
        ollama_p = self.manager._get_provider("ollama")
        openai_p = self.manager._get_provider("openai")
        gemini_p = self.manager._get_provider("gemini")

        self.assertEqual(ollama_p.__class__.__name__, "OllamaVisionProvider")
        self.assertEqual(openai_p.__class__.__name__, "OpenAIVisionProvider")
        self.assertEqual(gemini_p.__class__.__name__, "GeminiVisionProvider")

    def test_image_processing_pipeline(self):
        # PNG Magic Header
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        result = self.manager.process_image(png_bytes, "sample.png", "image/png")

        self.assertIsInstance(result, VisionResult)
        self.assertEqual(result.filename, "sample.png")
        self.assertEqual(result.file_type, "image/png")
        self.assertEqual(result.provider, "local")
        self.assertIsNotNone(result.ocr)

    def test_security_validation_executable_rejection(self):
        fake_exe_bytes = b"MZHeaderNotAllowed" + b"\x00" * 10
        with self.assertRaises(SecurityValidationError):
            self.manager.process_image(fake_exe_bytes, "malicious.exe", "application/octet-stream")

    def test_metrics_and_history(self):
        metrics = self.manager.get_metrics()
        self.assertIsNotNone(metrics)
        self.assertGreaterEqual(metrics.images_analyzed, 0)


if __name__ == "__main__":
    unittest.main()
