"""SQLite tabanlı belge ve parça deposu.

Tek bir dosyada tutulur (varsayılan: data/dayanak.sqlite3); kurulum
gerektirmez. Aynı içerik ikinci kez yüklenirse SHA-256 özetiyle fark edilir.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .chunking import Chunk

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    pages INTEGER NOT NULL,
    chunks INTEGER NOT NULL,
    words INTEGER NOT NULL,
    added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ord INTEGER NOT NULL,
    page INTEGER NOT NULL,
    heading TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
"""


@dataclass
class StoredChunk:
    id: int
    doc_id: int
    doc_name: str
    ord: int
    page: int
    heading: str
    text: str
    embedding: list[float] | None


@dataclass
class Document:
    id: int
    name: str
    sha256: str
    pages: int
    chunks: int
    words: int
    added_at: float


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
        self.version = 0  # her değişiklikte artar; arama indeksi yeniden kurulur

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def find_by_digest(self, sha: str) -> Document | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM documents WHERE sha256 = ?", (sha,)).fetchone()
        return Document(**dict(row)) if row else None

    def add(
        self,
        name: str,
        sha: str,
        pages: int,
        chunks: list[Chunk],
        embeddings: list[list[float]] | None = None,
    ) -> Document:
        words = sum(len(ch.text.split()) for ch in chunks)
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO documents(name, sha256, pages, chunks, words, added_at) VALUES (?,?,?,?,?,?)",
                (name, sha, pages, len(chunks), words, time.time()),
            )
            doc_id = cur.lastrowid
            c.executemany(
                "INSERT INTO chunks(doc_id, ord, page, heading, text, embedding) VALUES (?,?,?,?,?,?)",
                [
                    (doc_id, ch.ord, ch.page, ch.heading, ch.text, json.dumps(embeddings[i]) if embeddings else None)
                    for i, ch in enumerate(chunks)
                ],
            )
        self.version += 1
        doc = self.get(doc_id)
        assert doc is not None
        return doc

    def get(self, doc_id: int) -> Document | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return Document(**dict(row)) if row else None

    def documents(self) -> list[Document]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM documents ORDER BY added_at DESC, id DESC").fetchall()
        return [Document(**dict(r)) for r in rows]

    def delete(self, doc_id: int) -> bool:
        with self._conn() as c:
            n = c.execute("DELETE FROM documents WHERE id = ?", (doc_id,)).rowcount
        if n:
            self.version += 1
        return bool(n)

    def chunks(self) -> list[StoredChunk]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT c.*, d.name AS doc_name FROM chunks c JOIN documents d ON d.id = c.doc_id ORDER BY c.doc_id, c.ord"
            ).fetchall()
        return [
            StoredChunk(
                id=r["id"],
                doc_id=r["doc_id"],
                doc_name=r["doc_name"],
                ord=r["ord"],
                page=r["page"],
                heading=r["heading"],
                text=r["text"],
                embedding=json.loads(r["embedding"]) if r["embedding"] else None,
            )
            for r in rows
        ]

    def doc_chunks(self, doc_id: int) -> list[StoredChunk]:
        return [c for c in self.chunks() if c.doc_id == doc_id]
