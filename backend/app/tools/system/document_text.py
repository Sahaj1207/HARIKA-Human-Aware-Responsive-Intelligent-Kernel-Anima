"""The text inside a document, so HARIKA can answer questions about it.

PDF (pypdf), Word, PowerPoint and Excel (their XML, read straight from the zip), and
plain text formats. Everything is read on this computer; only the parts needed to
answer are later given to the language model. Nothing here runs anything in the file.
"""
import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree

READABLE = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".csv", ".json", ".log", ".rtf", ".xml", ".html", ".htm"}
_MAX_BYTES = 60 * 1024 * 1024
_MAX_PAGES = 400
_MAX_CHARS = 400_000


class UnreadableDocument(Exception):
    """Why a document's text can't be read (shown to the user)."""


@dataclass
class Document:
    path: Path
    # (label, text) per page / slide / sheet; label is e.g. "page 3", or "" for plain text files.
    sections: List[tuple] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(text for _, text in self.sections)


def read_document(path: Path) -> Document:
    suffix = path.suffix.lower()
    if suffix not in READABLE:
        raise UnreadableDocument(f"I can read PDF, Word, PowerPoint, Excel and text files, not {suffix or 'this kind of'} files")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise UnreadableDocument(f"I couldn't open {path.name}") from exc
    if size > _MAX_BYTES:
        raise UnreadableDocument(f"{path.name} is too large for me to read ({size // (1024 * 1024)} MB)")
    try:
        if suffix == ".pdf":
            sections = _pdf(path)
        elif suffix == ".docx":
            sections = [("", _xml_text(path, ["word/document.xml"], paragraph="p"))]
        elif suffix == ".pptx":
            sections = _slides(path)
        elif suffix == ".xlsx":
            sections = [("", _xml_text(path, ["xl/sharedStrings.xml"], paragraph="si"))]
        else:
            raw = path.read_text(encoding="utf-8", errors="replace")[:_MAX_CHARS]
            if suffix in (".html", ".htm", ".xml", ".rtf"):
                raw = re.sub(r"<[^>]+>|\\[a-z]+-?\d* ?|[{}]", " ", raw)
            sections = [("", raw)]
    except UnreadableDocument:
        raise
    except Exception as exc:
        raise UnreadableDocument(f"I couldn't read {path.name}; it may be damaged or password-protected") from exc
    sections = [(label, _clean(text)) for label, text in sections if _clean(text)]
    if not sections:
        hint = " It looks like scanned pages (pictures of text), which I can't read yet." if suffix == ".pdf" else ""
        raise UnreadableDocument(f"I couldn't find any text in {path.name}.{hint}")
    return Document(path, sections)


def _pdf(path: Path) -> List[tuple]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")  # many "protected" PDFs only restrict printing
        except Exception as exc:
            raise UnreadableDocument(f"{path.name} is password-protected") from exc
    sections, total = [], 0
    for number, page in enumerate(reader.pages[:_MAX_PAGES], 1):
        text = page.extract_text() or ""
        sections.append((f"page {number}", text))
        total += len(text)
        if total > _MAX_CHARS:
            break
    return sections


def _xml_text(path: Path, members: List[str], paragraph: str) -> str:
    """Text of Office XML parts, one line per paragraph (Word <w:p>, Excel <si>)."""
    out: List[str] = []
    with zipfile.ZipFile(path) as archive:
        for member in members:
            if member not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(member))
            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] == paragraph:
                    line = "".join(t.text or "" for t in element.iter() if t.tag.rsplit("}", 1)[-1] == "t")
                    if line.strip():
                        out.append(line)
    return "\n".join(out)[:_MAX_CHARS]


def _slides(path: Path) -> List[tuple]:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
    names.sort(key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)))
    return [(f"slide {i}", _xml_text(path, [name], paragraph="p")) for i, name in enumerate(names, 1)]


def _clean(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text or "")
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def passages(document: Document, size: int = 1200) -> List[tuple]:
    """(label, text) pieces of about `size` characters, each within one page/slide."""
    pieces = []
    for label, text in document.sections:
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):  # end at a sentence or line break when one is near
                cut = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
                if cut > start + size // 2:
                    end = cut + 1
            pieces.append((label, text[start:end].strip()))
            start = end
    return [p for p in pieces if p[1]]


def choose_passages(document: Document, question: str, budget: int = 9000, embedder=None) -> List[tuple]:
    """The parts of a long document that best answer the question, in document order.

    Short documents are used whole. Long ones give half the pieces closest in meaning to
    the question (or sharing its words, without the meaning model) and half spread
    evenly from the beginning.
    """
    pieces = passages(document)
    if sum(len(t) for _, t in pieces) <= budget:
        return pieces
    count = max(1, budget // 1200)
    scores: Optional[List[float]] = None
    if question and embedder is not None:
        vectors = embedder.embed([question] + [t for _, t in pieces])
        if vectors is not None:
            scores = list(vectors[1:] @ vectors[0])
    if scores is None and question:
        # Words found in few pieces say more than words found everywhere ("17" vs "topic").
        words = [set(re.findall(r"[a-z0-9]{2,}", t.lower())) for _, t in pieces]
        frequency: dict = {}
        for found in words:
            for word in found:
                frequency[word] = frequency.get(word, 0) + 1
        wanted = set(re.findall(r"[a-z0-9]{2,}", question.lower()))
        scores = [sum(math.log(len(pieces) / frequency[w]) for w in wanted & found) for found in words]
    step = len(pieces) / count
    spread = [int(i * step) for i in range(count)]  # the beginning and evenly through the rest
    if not scores or max(scores) <= 0:
        picked = spread
    else:
        # Half the most relevant pieces, half spread out: right for a pointed question and a summary alike.
        best = sorted(range(len(pieces)), key=lambda i: -scores[i])[: (count + 1) // 2]
        picked = list(dict.fromkeys(best + [i for i in spread if i not in best]))[:count]
    return [pieces[i] for i in sorted(picked)]
