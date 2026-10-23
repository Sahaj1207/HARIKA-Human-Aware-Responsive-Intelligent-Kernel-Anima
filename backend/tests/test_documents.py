"""Reading documents: text from each format, choosing passages, finding the file and answering (no real AI)."""
import asyncio
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.tools.productivity.documents_tool import DocumentsTool
from app.tools.system.document_text import Document, UnreadableDocument, choose_passages, passages, read_document

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def make_docx(path: Path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document {_W}><w:body>{body}</w:body></w:document>")


def make_pptx(path: Path, slides):
    with zipfile.ZipFile(path, "w") as z:
        for i, text in enumerate(slides, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", f"<p:sld xmlns:p='p' {_A}><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:sld>")


def make_pdf(path: Path, text: str):
    """A one-page PDF with a line of real text (no PDF library needed to write it)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))


class TextTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="harika-docs-"))

    def test_each_format(self):
        make_docx(self.dir / "lease.docx", ["Rental agreement", "The deposit is two months' rent."])
        self.assertIn("The deposit is two months' rent.", read_document(self.dir / "lease.docx").text)
        make_pptx(self.dir / "deck.pptx", ["Quarterly plan", "Hire two designers"])
        deck = read_document(self.dir / "deck.pptx")
        self.assertEqual([label for label, _ in deck.sections], ["slide 1", "slide 2"])
        make_pdf(self.dir / "notice.pdf", "Rent is due on the 5th")
        pdf = read_document(self.dir / "notice.pdf")
        self.assertEqual(pdf.sections[0][0], "page 1")
        self.assertIn("Rent is due on the 5th", pdf.text)
        (self.dir / "notes.md").write_text("# Ideas\nA trip to Goa", encoding="utf-8")
        self.assertIn("A trip to Goa", read_document(self.dir / "notes.md").text)

    def test_unreadable_files_say_why(self):
        (self.dir / "setup.exe").write_bytes(b"MZ")
        with self.assertRaisesRegex(UnreadableDocument, "not .exe files"):
            read_document(self.dir / "setup.exe")
        make_docx(self.dir / "empty.docx", [])
        with self.assertRaisesRegex(UnreadableDocument, "couldn't find any text"):
            read_document(self.dir / "empty.docx")
        (self.dir / "broken.pdf").write_bytes(b"not a pdf at all")
        with self.assertRaises(UnreadableDocument):
            read_document(self.dir / "broken.pdf")

    def test_passages_and_choosing(self):
        sections = [(f"page {i}", f"Page {i} talks about topic {i}. " * 40) for i in range(1, 21)]
        document = Document(Path("big.pdf"), sections)
        pieces = passages(document)
        self.assertTrue(all(len(text) <= 1200 for _, text in pieces))
        chosen = choose_passages(document, "what about topic 17?", budget=6000)
        labels = [label for label, _ in chosen]
        self.assertIn("page 17", labels)  # the relevant part
        self.assertIn("page 1", labels)   # and the beginning, for context
        self.assertEqual(labels, sorted(labels, key=lambda l: int(l.split()[1])))  # in document order
        small = Document(Path("small.txt"), [("", "Short note.")])
        self.assertEqual(choose_passages(small, "anything"), [("", "Short note.")])


class DocumentsToolTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="harika-docs-"))
        self.tool = DocumentsTool()
        self.asked = []

        async def ask(system, message):
            self.asked.append(message)
            return "[calm] The deposit is two months' rent (page 1)."
        self.tool._ask = ask

    def run_tool(self, **args):
        return asyncio.run(self.tool.execute(args))

    def test_answers_from_the_found_document(self):
        lease = self.dir / "Lease agreement.docx"
        make_docx(lease, ["The deposit is two months' rent."])
        with patch("app.tools.system.files.files_tool.search", return_value=[lease]):
            result = self.run_tool(operation="ask_file", target="lease", question="what about the deposit?")
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"], "From Lease agreement.docx:\n\nThe deposit is two months' rent (page 1).")
        self.assertIn("The deposit is two months' rent.", self.asked[0])
        self.assertIn("My question: what about the deposit?", self.asked[0])

    def test_latest_download_and_this_file(self):
        old, new = self.dir / "old.txt", self.dir / "invoice.txt"
        old.write_text("old", encoding="utf-8")
        new.write_text("Invoice total: 4,200", encoding="utf-8")
        (self.dir / "installer.exe").write_bytes(b"MZ")
        os.utime(old, (time.time() - 3600, time.time() - 3600))
        with patch("app.tools.system.files._known_folder", return_value=self.dir):
            self.assertEqual(self.tool.find("latest download")[0], new)
            self.run_tool(operation="ask_file", target="latest download")
        self.assertEqual(self.tool.find("this file")[0], new)  # remembered for the follow-up

    def test_missing_and_mismatched_files(self):
        with patch("app.tools.system.files.files_tool.search", return_value=[self.dir / "Notes.zip"]):
            result = self.run_tool(operation="ask_file", target="notes")
        self.assertFalse(result["success"])
        self.assertIn("couldn't find a document called 'notes'", result["error"])

    def test_compare_two_documents(self):
        a, b = self.dir / "resume old.docx", self.dir / "resume new.docx"
        make_docx(a, ["Skills: Python"])
        make_docx(b, ["Skills: Python, React"])
        with patch("app.tools.system.files.files_tool.search", side_effect=lambda q: [a] if "old" in q else [b]):
            result = self.run_tool(operation="compare_files", target="old resume", other="new resume")
        self.assertTrue(result["success"])
        self.assertIn("<first name=\"resume old.docx\">", self.asked[0])
        self.assertIn("<second name=\"resume new.docx\">", self.asked[0])


if __name__ == "__main__":
    unittest.main()
