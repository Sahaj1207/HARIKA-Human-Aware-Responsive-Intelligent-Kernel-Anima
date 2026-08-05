import unittest
from app.vision.pdf import pdf_engine, PDFEngine
from app.vision.schemas import PDFAnalysisResult
from app.planning.events import planning_event_bus, PlanningEventType


class TestVisionPDF(unittest.TestCase):

    def test_pdf_parsing_and_events(self):
        events = []
        planning_event_bus.subscribe(PlanningEventType.PDF_PROCESSED, lambda et, p: events.append((et, p)))

        pdf_header_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\n(Invoice Total $1500) Tj"
        result = pdf_engine.parse_pdf(pdf_header_bytes, "invoice.pdf")

        self.assertIsInstance(result, PDFAnalysisResult)
        self.assertEqual(result.filename, "invoice.pdf")
        self.assertGreaterEqual(result.total_pages, 1)
        self.assertIn("Invoice Total $1500", result.extracted_text)
        self.assertTrue(len(events) > 0)


if __name__ == "__main__":
    unittest.main()
