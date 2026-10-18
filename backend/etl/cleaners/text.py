"""Text cleaning, language detection and chunking."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    """Normalise unicode, drop control characters and repair hard line wraps; keep paragraph breaks."""
    t = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    t = _CTRL.sub("", t).replace("­", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)            # de-hyphenate wrapped words
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"(?<!\n)\n(?!\n)", " ", t)           # single newlines -> spaces
    t = re.sub(r"\n{3,}", "\n\n", t)
    return "\n\n".join(p.strip() for p in t.split("\n\n") if p.strip())


def detect_language(text: str) -> str:
    """'en', 'ta' or 'mixed' by share of Tamil letters among letters."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    share = sum("஀" <= c <= "௿" for c in letters) / len(letters)
    return "ta" if share > 0.7 else "mixed" if share > 0.1 else "en"


@dataclass(frozen=True)
class Chunk:
    number: int
    page: int
    text: str


def chunk_pages(pages: list[str], max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    """Paragraph-aware chunks that never cross a page; over-long paragraphs are split with overlap."""
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")
    chunks: list[Chunk] = []
    for pno, raw in enumerate(pages, 1):
        text = clean_text(raw)
        pieces: list[str] = []
        for para in text.split("\n\n"):
            while len(para) > max_chars:
                cut = max(para.rfind(". ", 0, max_chars), para.rfind(" ", 0, max_chars))
                cut = cut if cut > max_chars // 2 else max_chars
                pieces.append(para[: cut + 1].strip())
                para = para[max(cut + 1 - overlap, 1):].strip()
            if para:
                pieces.append(para)
        buf = ""
        for piece in pieces:
            if buf and len(buf) + len(piece) + 2 > max_chars:
                chunks.append(Chunk(len(chunks), pno, buf))
                buf = ""
            buf = f"{buf}\n\n{piece}" if buf else piece
        if buf:
            chunks.append(Chunk(len(chunks), pno, buf))
    return chunks
