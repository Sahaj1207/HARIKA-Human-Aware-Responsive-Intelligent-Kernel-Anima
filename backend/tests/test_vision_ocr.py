import unittest
from app.vision.ocr import ocr_engine, OCREngine
from app.vision.schemas import OCRResult, OCRBlock
from app.planning.events import planning_event_bus, PlanningEventType


class TestVisionOCR(unittest.TestCase):

    def test_ocr_line_classification(self):
        engine = OCREngine()
        self.assertEqual(engine._classify_line("def main():"), "code")
        self.assertEqual(engine._classify_line("1,250.00"), "number")
        self.assertEqual(engine._classify_line("Name | Price | Qty"), "table")
        self.assertEqual(engine._classify_line("Click Submit Button"), "ui")
        self.assertEqual(engine._classify_line("Standard paragraph text line."), "text")

    def test_ocr_process_asset(self):
        events = []
        planning_event_bus.subscribe(PlanningEventType.OCR_COMPLETED, lambda et, p: events.append((et, p)))

        sample_bytes = b"Total: $500\ndef process():\n  return True\nSubmit Form"
        result = ocr_engine.process_asset(sample_bytes, "image/png")

        self.assertIsInstance(result, OCRResult)
        self.assertGreater(len(result.blocks), 0)
        self.assertGreater(result.word_count, 0)
        self.assertTrue(len(events) > 0)


if __name__ == "__main__":
    unittest.main()
