"""Cevap üretimi: alıntı tabanlı (LLM'siz) veya LLM ile.

Alıntı tabanlı mod (extractive): en alakalı parçalardan soruyla en çok
örtüşen cümleleri seçer ve kaynağıyla birlikte aynen verir. Uydurma
imkânsızdır ama cevap kaynakların diliyle sınırlıdır.

LLM modu: en alakalı parçalar numaralandırılıp modele verilir; modelden
yalnızca bu kaynaklara dayanarak, her cümlenin sonuna [n] koyarak cevap
vermesi istenir. Ardından verify.py her cümleyi kaynağıyla karşılaştırır.
"""

from __future__ import annotations

from .schema import Citation
from .search import BM25, Hit
from .text import sentences, terms
from .verify import ABSTAIN_PHRASE

# Bu skorun altındaki en iyi arama sonucu "belgelerde yok" kabul edilir.
# Değer evals/ altındaki sorularla ayarlanmıştır.
MIN_BM25 = 3.0
MIN_COVERAGE = 0.55
MAX_SENTENCES = 3

SYSTEM_PROMPT = f"""Sen bir şirketin iç belgeleri hakkında soruları yanıtlayan bir asistansın.
Kurallar:
- YALNIZCA aşağıda numaralandırılmış kaynaklardaki bilgileri kullan. Genel bilgini kullanma.
- Her cümlenin sonuna dayandığı kaynağın numarasını köşeli parantezle yaz: [1] veya [1, 3].
- Sayıları, tutarları ve süreleri kaynakta yazdığı gibi aktar; hesaplama yapıp yeni sayı üretme.
- Kısa ve net cevap ver (en fazla 4 cümle).
- Cevap kaynaklarda yoksa yalnızca şunu yaz: "{ABSTAIN_PHRASE}"
- Soru hangi dildeyse o dilde cevap ver."""


def to_citations(hits: list[Hit]) -> list[Citation]:
    return [
        Citation(
            n=i,
            chunk_id=h.chunk.id,
            doc_id=h.chunk.doc_id,
            doc_name=h.chunk.doc_name,
            page=h.chunk.page,
            heading=h.chunk.heading,
            text=h.chunk.text,
            score=round(h.score, 5),
        )
        for i, h in enumerate(hits, 1)
    ]


def should_abstain(hits: list[Hit]) -> bool:
    if not hits:
        return True
    best = hits[0]
    if best.vector is not None and best.vector >= 0.62:
        return False
    return best.bm25 < MIN_BM25


def extractive(question: str, hits: list[Hit], bm25: BM25) -> str:
    """Soruyla en çok örtüşen 1-3 cümleyi kaynak numarasıyla döndürür."""
    q = set(terms(question))
    if not q:
        return ABSTAIN_PHRASE
    weight = {t: bm25.idf.get(t, 0.5) for t in q}
    total = sum(weight.values()) or 1.0
    scored: list[tuple[float, int, int, str]] = []
    for n, h in enumerate(hits[:3], 1):
        heading_terms = set(terms(h.chunk.heading))
        for pos, s in enumerate(sentences(h.chunk.text)):
            st = set(terms(s)) | heading_terms
            cov = sum(weight[t] for t in q & st) / total
            # biraz rank cezası: üstteki parçalar tercih edilir
            scored.append((cov - 0.04 * (n - 1), n, pos, s))
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < MIN_COVERAGE:
        return ABSTAIN_PHRASE
    best = scored[0][0]
    picked = [x for x in scored if x[0] >= best * 0.75][:MAX_SENTENCES]
    picked.sort(key=lambda x: (x[1], x[2]))  # okunuş sırası
    out = []
    for _, n, _, s in picked:
        s = s.rstrip()
        if s[-1] not in ".!?:":
            s += "."
        out.append(f"{s[:-1]} [{n}]{s[-1]}")
    return " ".join(out)


def build_prompt(question: str, citations: list[Citation]) -> str:
    sources = "\n\n".join(
        f"[{c.n}] ({c.doc_name}{' — ' + c.heading if c.heading else ''})\n{c.text}" for c in citations
    )
    return f"KAYNAKLAR:\n\n{sources}\n\nSORU: {question}"
