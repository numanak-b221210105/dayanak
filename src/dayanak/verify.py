"""Dayanak doğrulaması: cevaptaki her cümle gösterdiği kaynakla desteklenmiş mi?

LLM'ler akıcı ama uydurma cevaplar üretebilir. Bu modül, cevabı cümlelere
böler ve her cümle için şunlara bakar:

1. Kaynak gösterilmiş mi? ([1], [2] ...)
2. Gösterilen kaynak numarası gerçekten var mı?
3. Cümledeki anlamlı terimlerin ne kadarı o kaynakta geçiyor? (support)
4. Cümledeki her sayı kaynakta da geçiyor mu? Uydurulan bir tutar, süre
   veya oran en tehlikeli halüsinasyon türüdür; tek başına başarısızlık
   sebebidir.

Bu, anlamsal bir kanıt değil, ucuz ve açıklanabilir bir ilk savunma hattıdır.
"""

from __future__ import annotations

import re

from .schema import Citation, SentenceCheck
from .text import numbers, sentences, terms

SUPPORT_THRESHOLD = 0.6
ABSTAIN_PHRASE = "Bu soruya belgelerde bir dayanak bulamadım."
_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def is_abstention(text: str) -> bool:
    t = text.lower()
    return "dayanak bulamadım" in t or "bilgi bulunmamaktadır" in t or "not found in the" in t


def split_cited(answer: str) -> list[tuple[str, list[int]]]:
    """Cevabı (temiz cümle, kaynak numaraları) çiftlerine böler."""
    out = []
    for s in sentences(answer):
        cites = sorted({int(n) for grp in _CITE.findall(s) for n in grp.split(",")})
        clean = _CITE.sub("", s).replace(" .", ".").strip()
        if clean:
            out.append((clean, cites))
    return out


def check(answer: str, citations: list[Citation]) -> tuple[list[SentenceCheck], float | None, list[str]]:
    by_n = {c.n: c for c in citations}
    checks: list[SentenceCheck] = []
    warnings: list[str] = []
    for text, cites in split_cited(answer):
        if is_abstention(text):
            continue
        bad = [n for n in cites if n not in by_n]
        if bad:
            warnings.append(f"Var olmayan kaynak numarası: {', '.join(f'[{n}]' for n in bad)}")
        valid = [n for n in cites if n in by_n]
        src = "\n".join(f"{by_n[n].heading}\n{by_n[n].text}" for n in valid)
        sent_terms = set(terms(text))
        support = len(sent_terms & set(terms(src))) / len(sent_terms) if sent_terms and src else 0.0
        missing = sorted(numbers(text) - numbers(src)) if src else sorted(numbers(text))
        if not valid:
            reason = "Kaynak gösterilmemiş"
        elif missing:
            reason = "Kaynakta geçmeyen sayı: " + ", ".join(missing)
        elif support < SUPPORT_THRESHOLD:
            reason = f"Kaynakla örtüşme düşük (%{round(support * 100)})"
        else:
            reason = None
        checks.append(
            SentenceCheck(
                text=text,
                cites=valid,
                supported=reason is None,
                support=round(support, 3),
                missing_numbers=missing,
                reason=reason,
            )
        )
    grounded = round(sum(c.supported for c in checks) / len(checks), 3) if checks else None
    return checks, grounded, warnings
