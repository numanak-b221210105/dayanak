"""API ve çekirdek arasında paylaşılan veri modelleri."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["auto", "extractive", "llm"]


class Citation(BaseModel):
    n: int = Field(description="Cevapta [n] olarak geçen kaynak numarası")
    chunk_id: int
    doc_id: int
    doc_name: str
    page: int
    heading: str
    text: str
    score: float


class SentenceCheck(BaseModel):
    """Cevaptaki bir cümlenin dayanak kontrolü."""

    text: str
    cites: list[int]
    supported: bool
    support: float = Field(description="Cümledeki terimlerin gösterilen kaynakta geçme oranı (0-1)")
    missing_numbers: list[str] = Field(default_factory=list, description="Kaynakta bulunmayan sayılar")
    reason: str | None = None


class Answer(BaseModel):
    question: str
    answer: str
    mode: Literal["extractive", "llm"]
    abstained: bool
    sentences: list[SentenceCheck]
    citations: list[Citation]
    groundedness: float | None = Field(description="Dayanağı doğrulanan cümle oranı")
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int
    query_id: int | None = Field(default=None, description="Geri bildirim için sorgu kaydı numarası")


class DocumentOut(BaseModel):
    id: int
    name: str
    pages: int
    chunks: int
    words: int
    added_at: float


class SearchHit(BaseModel):
    rank: int
    score: float
    bm25: float
    vector: float | None
    citation: Citation


class DayCount(BaseModel):
    date: str
    count: int


class DocCount(BaseModel):
    doc_id: int
    name: str
    count: int


class Gap(BaseModel):
    question: str
    count: int
    last_ts: float


class QueryLog(BaseModel):
    id: int
    ts: float
    question: str
    mode: str
    abstained: bool
    groundedness: float | None
    elapsed_ms: int
    feedback: int | None


class Insights(BaseModel):
    total: int
    answered: int
    abstained: int
    abstain_rate: float | None
    avg_groundedness: float | None
    avg_ms: float | None
    feedback_up: int
    feedback_down: int
    by_day: list[DayCount]
    top_docs: list[DocCount]
    gaps: list[Gap] = Field(description="Belgelerde cevabı bulunamayan sorular: eksik doküman sinyali")
    recent: list[QueryLog]
