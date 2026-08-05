import os
import shutil
import tempfile
import unittest
from pathlib import Path
from app.vision.manager import VisionManager
from app.vision.history import VisionHistoryManager
from app.vision.metrics import VisionMetricsManager
from app.vision.schemas import VisionResult, VisionMetrics
from app.planning.events import planning_event_bus, PlanningEventType


class TestVisionAllE2E(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.history_file = Path(self.test_dir) / "vision_history.json"
        self.history = VisionHistoryManager(storage_file=self.history_file)
        self.metrics = VisionMetricsManager(history=self.history)
        self.manager = VisionManager(history=self.history, metrics=self.metrics)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_e2e_png_analysis_and_events(self):
        started = []
        completed = []
        planning_event_bus.subscribe(PlanningEventType.VISION_STARTED, lambda et, p: started.append(p))
        planning_event_bus.subscribe(PlanningEventType.VISION_COMPLETED, lambda et, p: completed.append(p))

        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        res = self.manager.process_image(png_bytes, "app_dashboard_ui.png", "image/png")

        self.assertEqual(res.filename, "app_dashboard_ui.png")
        self.assertEqual(res.image_analysis.classification, "ui")
        self.assertTrue(len(started) > 0)
        self.assertTrue(len(completed) > 0)

    def test_e2e_pdf_analysis_and_history_persistence(self):
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n(Resume John Doe) Tj"
        res = self.manager.process_pdf(pdf_bytes, "resume.pdf", "application/pdf")

        self.assertEqual(res.filename, "resume.pdf")
        self.assertIn("Resume John Doe", res.pdf_analysis.extracted_text)

        # Check persistence
        history = self.manager.get_history()
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["filename"], "resume.pdf")

    def test_e2e_metrics_tracking(self):
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n(Invoice Text) Tj"

        self.manager.process_image(png_bytes, "img1.png", "image/png")
        self.manager.process_pdf(pdf_bytes, "doc1.pdf", "application/pdf")

        metrics = self.manager.get_metrics()
        self.assertIsInstance(metrics, VisionMetrics)
        self.assertGreaterEqual(metrics.images_analyzed, 1)
        self.assertGreaterEqual(metrics.pdfs_processed, 1)
        self.assertIn("local", metrics.provider_usage)


if __name__ == "__main__":
    unittest.main()
