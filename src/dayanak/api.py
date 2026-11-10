"""REST API.  Çalıştırma: python -m dayanak.serve"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import __version__, llm
from .answer import to_citations
from .engine import DuplicateDocument, Engine
from .loaders import SUPPORTED, UnsupportedFile
from .schema import Answer, DocumentOut, Mode, SearchHit

app = FastAPI(
    title="Dayanak",
    version=__version__,
    description="Answers from your documents — every sentence cited and checked. "
    "Belgelerinizden kaynak gösteren ve her cümlesini doğrulayan soru-cevap.",
)
STATIC = Path(__file__).parent / "static"
MAX_BYTES = 20 * 1024 * 1024


@lru_cache(maxsize=1)
def engine() -> Engine:
    return Engine()


class AskRequest(BaseModel):
    question: str
    mode: Mode = "auto"
    k: int = 4


class LLMStatus(BaseModel):
    host: str
    model: str
    embed_model: str
    reachable: bool


class Status(BaseModel):
    version: str
    documents: int
    chunks: int
    vector_search: bool
    llm: LLMStatus


def _doc_out(d) -> DocumentOut:
    return DocumentOut(id=d.id, name=d.name, pages=d.pages, chunks=d.chunks, words=d.words, added_at=d.added_at)


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/status", response_model=Status)
def status() -> Status:
    eng = engine()
    chunks = eng.index().chunks
    cfg = eng.cfg
    return Status(
        version=__version__,
        documents=len(eng.store.documents()),
        chunks=len(chunks),
        vector_search=any(c.embedding for c in chunks),
        llm=LLMStatus(
            host=urlparse(cfg.llm_base_url).netloc or cfg.llm_base_url,
            model=cfg.llm_model,
            embed_model=cfg.embed_model,
            reachable=llm.reachable(cfg),
        ),
    )


@app.get("/documents", response_model=list[DocumentOut])
def list_documents() -> list[DocumentOut]:
    return [_doc_out(d) for d in engine().store.documents()]


@app.post("/documents", response_model=list[DocumentOut], status_code=201)
async def upload(files: list[UploadFile] = File(...)) -> list[DocumentOut]:
    out = []
    for f in files:
        name = f.filename or "belge"
        data = await f.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"{name}: dosya 20 MB'tan büyük")
        try:
            out.append(_doc_out(engine().add(name, data)))
        except DuplicateDocument as e:
            raise HTTPException(409, str(e)) from e
        except UnsupportedFile as e:
            raise HTTPException(415, str(e)) from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    return out


@app.post("/documents/samples", response_model=list[DocumentOut], status_code=201)
def load_samples() -> list[DocumentOut]:
    """Kurgusal bir şirketin 4 iç yönetmeliğini demo olarak yükler."""
    return [_doc_out(d) for d in engine().add_samples()]


@app.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int) -> None:
    if not engine().store.delete(doc_id):
        raise HTTPException(404, "Belge bulunamadı")


@app.get("/documents/{doc_id}/chunks")
def document_chunks(doc_id: int) -> list[dict]:
    eng = engine()
    if not eng.store.get(doc_id):
        raise HTTPException(404, "Belge bulunamadı")
    return [{"id": c.id, "page": c.page, "heading": c.heading, "text": c.text} for c in eng.store.doc_chunks(doc_id)]


@app.get("/search", response_model=list[SearchHit])
def search(q: str = Query(..., min_length=2), k: int = Query(5, ge=1, le=20)) -> list[SearchHit]:
    hits = engine().search(q, k=k)
    cites = to_citations(hits)
    return [
        SearchHit(rank=h.rank, score=round(h.score, 5), bm25=round(h.bm25, 3), vector=h.vector, citation=c)
        for h, c in zip(hits, cites, strict=True)
    ]


@app.post("/ask", response_model=Answer)
def ask(req: AskRequest) -> Answer:
    q = req.question.strip()
    if len(q) < 2:
        raise HTTPException(422, "Soru boş")
    if not engine().store.documents():
        raise HTTPException(409, "Henüz belge yok. Önce belge yükleyin veya demo belgelerini ekleyin.")
    return engine().ask(q, mode=req.mode, k=max(1, min(req.k, 8)))


@app.get("/formats")
def formats() -> list[str]:
    return list(SUPPORTED)
