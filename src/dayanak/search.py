"""Hibrit arama: BM25 (anahtar kelime) + vektör benzerliği, RRF ile birleştirilir.

- BM25 her zaman çalışır; ek bir servis gerektirmez.
- Bir embedding servisi (ör. Ollama'da nomic-embed-text) erişilebilirse
  anlamsal arama da devreye girer; böylece "yıllık izin" sorusu "tatil
  hakkı" geçen paragrafı da bulabilir.
- İki sıralama Reciprocal Rank Fusion ile birleştirilir: skorların
  ölçeklerini eşitlemeye gerek kalmadan sağlam bir birleşim verir.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .store import StoredChunk
from .text import terms

K1, B = 1.4, 0.72
RRF_K = 60


@dataclass
class Hit:
    chunk: StoredChunk
    score: float  # birleşik (RRF) skor
    bm25: float
    vector: float | None
    rank: int = 0


class BM25:
    def __init__(self, chunks: list[StoredChunk]) -> None:
        self.chunks = chunks
        # başlık da aranabilir metnin parçasıdır
        self.docs = [Counter(terms(f"{c.heading}\n{c.text}")) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = set(terms(query))
        out = []
        for d, length in zip(self.docs, self.lengths, strict=True):
            s = 0.0
            for t in q:
                tf = d.get(t)
                if tf:
                    s += self.idf[t] * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / (self.avg or 1)))
            out.append(s)
        return out


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class Index:
    def __init__(self, chunks: list[StoredChunk]) -> None:
        self.chunks = chunks
        self.bm25 = BM25(chunks)

    def search(
        self, query: str, k: int = 5, query_vec: list[float] | None = None, doc_ids: set[int] | None = None
    ) -> list[Hit]:
        """doc_ids verilirse yalnızca o belgelerin parçaları aranır (kapsam)."""
        if not self.chunks:
            return []
        bm = self.bm25.scores(query)
        allowed = [i for i, c in enumerate(self.chunks) if doc_ids is None or c.doc_id in doc_ids]
        bm_rank = sorted(allowed, key=lambda i: -bm[i])
        fused: dict[int, float] = {}
        for r, i in enumerate(bm_rank):
            if bm[i] > 0:
                fused[i] = fused.get(i, 0) + 1 / (RRF_K + r + 1)

        vec: list[float | None] = [None] * len(self.chunks)
        if query_vec is not None:
            for i in allowed:
                c = self.chunks[i]
                if c.embedding:
                    vec[i] = cosine(query_vec, c.embedding)
            vec_rank = sorted((i for i in range(len(vec)) if vec[i] is not None), key=lambda i: -(vec[i] or 0))
            for r, i in enumerate(vec_rank[: max(k * 4, 20)]):
                fused[i] = fused.get(i, 0) + 1 / (RRF_K + r + 1)

        ranked = sorted(fused, key=lambda i: -fused[i])[:k]
        return [
            Hit(chunk=self.chunks[i], score=fused[i], bm25=bm[i], vector=vec[i], rank=r + 1)
            for r, i in enumerate(ranked)
        ]
