"""Belge okuyucular: PDF, DOCX, Markdown, TXT.

Her okuyucu (sayfa_no, metin) çiftleri döndürür. Sayfa kavramı olmayan
biçimlerde tüm metin tek "sayfa" (1) kabul edilir; kaynak gösterirken
PDF'lerde sayfa numarası verilebilmesi için bu ayrım tutulur.
"""

from __future__ import annotations

from io import BytesIO

SUPPORTED = (".pdf", ".docx", ".md", ".txt")


class UnsupportedFile(ValueError):
    pass


def load(name: str, data: bytes) -> list[tuple[int, str]]:
    lower = name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]
    if lower.endswith(".docx"):
        import docx

        document = docx.Document(BytesIO(data))
        lines = []
        for p in document.paragraphs:
            style = (p.style.name or "").lower() if p.style is not None else ""
            prefix = "# " if style.startswith(("heading", "başlık")) else ""
            lines.append(prefix + p.text)
        return [(1, "\n".join(lines))]
    if lower.endswith((".md", ".txt")):
        return [(1, data.decode("utf-8", errors="replace"))]
    raise UnsupportedFile(f"{name}: desteklenen biçimler {', '.join(SUPPORTED)}")
