"""PDF text extraction (PyMuPDF). Scanned/image-only PDFs yield status 'empty' - no OCR is attempted."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Extraction:
    status: str                      # ok | empty | failed
    pages: list[str] = field(default_factory=list)
    page_count: int = 0
    error: str | None = None


def extract_pdf(content: bytes, min_chars: int = 40) -> Extraction:
    try:
        import pymupdf
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as e:  # noqa: BLE001 - corrupt input must not crash the run
        return Extraction("failed", error=f"{type(e).__name__}: {e}")
    try:
        if doc.needs_pass:
            return Extraction("failed", page_count=doc.page_count, error="PDF is password protected")
        pages = [doc[i].get_text("text") for i in range(doc.page_count)]
    except Exception as e:  # noqa: BLE001
        return Extraction("failed", page_count=getattr(doc, "page_count", 0), error=f"{type(e).__name__}: {e}")
    finally:
        doc.close()
    if sum(len(p.strip()) for p in pages) < min_chars:
        return Extraction("empty", pages, len(pages), "no extractable text (scanned image PDF? OCR not performed)")
    if readable_share(pages) < MIN_READABLE_SHARE:
        # e.g. legacy (non-Unicode) Tamil fonts extract as punctuation/symbols; indexing that would be noise
        return Extraction("empty", pages, len(pages),
                          "text layer is unreadable (non-Unicode font encoding?); OCR not performed")
    return Extraction("ok", pages, len(pages))


MIN_READABLE_SHARE = 0.5


def readable_share(pages: list[str]) -> float:
    """Share of non-space characters that are letters or digits (any script)."""
    chars = [c for p in pages for c in p if not c.isspace()]
    return sum(c.isalnum() for c in chars) / len(chars) if chars else 0.0
