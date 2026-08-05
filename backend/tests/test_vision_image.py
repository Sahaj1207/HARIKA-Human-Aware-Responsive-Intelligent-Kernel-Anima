import unittest
from app.vision.image_analyzer import image_analyzer
from app.vision.caption import caption_engine
from app.vision.schemas import ImageAnalysisResult, CaptionResult, OCRResult, OCRBlock


class TestVisionImage(unittest.TestCase):

    def test_image_classification(self):
        self.assertEqual(image_analyzer.classify_image("sales_chart.png", "image/png"), "chart")
        self.assertEqual(image_analyzer.classify_image("user_flowchart.png", "image/png"), "flowchart")
        self.assertEqual(image_analyzer.classify_image("arch_diagram.png", "image/png"), "diagram")
        self.assertEqual(image_analyzer.classify_image("main.py.png", "image/png"), "code")

    def test_image_analysis(self):
        res = image_analyzer.analyze(b"fakebytes", "dashboard_ui.png", "image/png")
        self.assertIsInstance(res, ImageAnalysisResult)
        self.assertEqual(res.classification, "ui")
        self.assertIn("dimensions", res.model_dump())

    def test_caption_generation(self):
        ocr = OCRResult(raw_text="Sample text", blocks=[], word_count=2)
        analysis = image_analyzer.analyze(b"fakebytes", "chart.png", "image/png", ocr)
        caption = caption_engine.generate_caption("chart.png", "image/png", analysis, ocr)

        self.assertIsInstance(caption, CaptionResult)
        self.assertIn("multimodal", caption.tags)
        self.assertIn("chart", caption.caption.lower())


if __name__ == "__main__":
    unittest.main()
