"""Belgeyi aranabilir parçalara (chunk) böler.

Kurallar:
- Paragraf sınırlarına saygı duyulur; bir paragraf ortadan bölünmez
  (çok uzun değilse).
- Her parça en yakın başlığı taşır; başlık hem aramaya katılır hem de
  kaynak gösterirken kullanıcıya "hangi bölüm" bilgisini verir.
- Parçalar arasında küçük bir örtüşme bırakılır; böylece iki parçanın
  sınırına düşen bilgi kaybolmaz.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TARGET_WORDS = 110
MAX_WORDS = 180
OVERLAP_SENTENCES = 1

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass
class Chunk:
    ord: int
    page: int
    heading: str
    text: str


def _paragraphs(text: str) -> list[tuple[str | None, str]]:
    """(başlık, paragraf) çiftleri; başlık satırları ayrı öğe olarak döner."""
    out: list[tuple[str | None, str]] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        body: list[str] = []
        for line in lines:
            if m := _HEADING.match(line):
                if body:
                    out.append((None, "\n".join(body)))
                    body = []
                out.append((m.group(2).strip(), ""))
            else:
                body.append(line)
        if body:
            out.append((None, "\n".join(body)))
    return out


def chunk_pages(pages: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    heading = ""
    buf: list[str] = []  # bu parçaya ait yeni paragraflar
    carry = ""  # önceki parçadan taşınan örtüşme cümlesi
    buf_page = 1

    def size() -> int:
        return sum(len(b.split()) for b in buf)

    def flush() -> None:
        nonlocal buf, carry
        if not buf:
            return
        text = "\n".join(([carry] if carry else []) + buf).strip()
        chunks.append(Chunk(ord=len(chunks), page=buf_page, heading=heading, text=text))
        tail = re.split(r"(?<=[.!?])\s+", buf[-1].strip())[-OVERLAP_SENTENCES:]
        carry = " ".join(tail) if len(" ".join(tail).split()) < 40 else ""
        buf = []

    for page_no, page_text in pages:
        for head, para in _paragraphs(page_text):
            if head is not None:
                flush()
                heading, carry, buf_page = head, "", page_no
                continue
            if buf and size() + len(para.split()) > MAX_WORDS:
                flush()
            if not buf:
                buf_page = page_no
            buf.append(para)
            if size() >= TARGET_WORDS:
                flush()
    flush()
    return chunks
