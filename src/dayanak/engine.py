"""Dayanak motoru: belgeleri ekler, arar ve dayanaklı cevap üretir."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from . import llm
from .answer import SYSTEM_PROMPT, build_prompt, extractive, should_abstain, to_citations
from .chunking import chunk_pages
from .config import Settings, settings
from .loaders import load
from .schema import Answer, Mode
from .search import Hit, Index
from .store import Document, Store
from .verify import ABSTAIN_PHRASE, check, is_abstention

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


class DuplicateDocument(ValueError):
    def __init__(self, doc: Document) -> None:
        super().__init__(f"Bu belge zaten yüklü: {doc.name}")
        self.doc = doc


class Engine:
    def __init__(self, cfg: Settings | None = None, llm_client: Any | None = None) -> None:
        self.cfg = cfg or settings()
        self.store = Store(self.cfg.db_path)
        self.llm_client = llm_client  # testlerde sahte istemci verilebilir
        self._index: Index | None = None
        self._index_version = -1
        self._lock = threading.Lock()

    # ---------- belgeler ----------
    def add(self, name: str, data: bytes, embed: bool = True) -> Document:
        sha = Store.digest(data)
        if existing := self.store.find_by_digest(sha):
            raise DuplicateDocument(existing)
        pages = load(name, data)
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError(f"{name}: belgeden metin çıkarılamadı (taranmış PDF olabilir)")
        vectors = llm.embed(self.cfg, [f"{c.heading}\n{c.text}" for c in chunks]) if embed else None
        return self.store.add(name, sha, len(pages), chunks, vectors)

    def add_samples(self) -> list[Document]:
        added = []
        for f in sorted(SAMPLES_DIR.glob("*.md")):
            try:
                added.append(self.add(f.name, f.read_bytes()))
            except DuplicateDocument:
                pass
        return added

    # ---------- arama ----------
    def index(self) -> Index:
        with self._lock:
            if self._index is None or self._index_version != self.store.version:
                self._index = Index(self.store.chunks())
                self._index_version = self.store.version
            return self._index

    def search(self, query: str, k: int = 5, doc_ids: set[int] | None = None) -> list[Hit]:
        idx = self.index()
        qvec = None
        if any(c.embedding for c in idx.chunks):
            vecs = llm.embed(self.cfg, [query])
            qvec = vecs[0] if vecs else None
        return idx.search(query, k=k, query_vec=qvec, doc_ids=doc_ids)

    # ---------- cevap ----------
    def llm_available(self) -> bool:
        return self.llm_client is not None or llm.reachable(self.cfg)

    def ask(
        self, question: str, mode: Mode = "auto", k: int = 4, doc_ids: set[int] | None = None, log: bool = True
    ) -> Answer:
        t0 = time.perf_counter()
        hits = self.search(question, k=k, doc_ids=doc_ids)
        citations = to_citations(hits)
        warnings: list[str] = []
        use_llm = mode == "llm" or (mode == "auto" and self.llm_available())

        if should_abstain(hits):
            text, used = ABSTAIN_PHRASE, "extractive"
        elif use_llm:
            try:
                text = llm.chat(self.cfg, SYSTEM_PROMPT, build_prompt(question, citations), self.llm_client)
                used = "llm"
            except Exception as e:  # noqa: BLE001
                warnings.append(f"LLM kullanılamadı ({type(e).__name__}); alıntı tabanlı cevap verildi.")
                text, used = extractive(question, hits, self.index().bm25), "extractive"
        else:
            text, used = extractive(question, hits, self.index().bm25), "extractive"

        abstained = is_abstention(text)
        checks, grounded, check_warnings = check(text, citations)
        warnings += check_warnings
        if checks and grounded is not None and grounded < 1:
            warnings.append(f"{sum(not c.supported for c in checks)} cümlenin dayanağı doğrulanamadı.")
        elapsed = round((time.perf_counter() - t0) * 1000)
        cited = sorted({citations[n - 1].doc_id for s in checks for n in s.cites if 0 < n <= len(citations)})
        qid = (
            self.store.log_query(question, used, abstained, None if abstained else grounded, elapsed, cited)
            if log
            else None
        )
        return Answer(
            question=question,
            answer=text.strip(),
            mode=used,  # type: ignore[arg-type]
            abstained=abstained,
            sentences=checks,
            citations=[] if abstained else citations,
            groundedness=None if abstained else grounded,
            warnings=warnings,
            elapsed_ms=elapsed,
            query_id=qid,
        )
