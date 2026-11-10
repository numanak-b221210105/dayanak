import io

import docx
import pytest
from fastapi.testclient import TestClient

from dayanak import api
from dayanak.engine import Engine

from .conftest import cfg


@pytest.fixture
def client(tmp_path, monkeypatch):
    eng = Engine(cfg(tmp_path))
    monkeypatch.setattr(api, "engine", lambda: eng)
    return TestClient(api.app)


def test_ui_and_health(client):
    assert "Dayanak" in client.get("/").text
    assert client.get("/health").json()["status"] == "ok"


def test_ask_without_documents_is_409(client):
    assert client.post("/ask", json={"question": "Merhaba?"}).status_code == 409


def test_samples_then_ask(client):
    r = client.post("/documents/samples")
    assert r.status_code == 201 and len(r.json()) == 4
    a = client.post("/ask", json={"question": "Babalık izni kaç gün?", "mode": "extractive"}).json()
    assert "5 iş günü" in a["answer"] and a["groundedness"] == 1.0
    s = client.get("/status").json()
    assert s["documents"] == 4 and s["llm"]["reachable"] is False


def test_upload_docx_search_and_delete(client):
    d = docx.Document()
    d.add_heading("Otopark Kuralları", level=1)
    d.add_paragraph("Çalışan otoparkı hafta içi 07.00 ile 20.00 arasında açıktır. Ziyaretçiler B katını kullanır.")
    buf = io.BytesIO()
    d.save(buf)
    r = client.post("/documents", files={"files": ("otopark.docx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 201
    doc_id = r.json()[0]["id"]
    hits = client.get("/search", params={"q": "ziyaretçi otoparkı"}).json()
    assert hits[0]["citation"]["heading"] == "Otopark Kuralları"
    assert client.post("/documents", files={"files": ("x.docx", buf.getvalue(), "x")}).status_code == 409
    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get("/documents").json() == []


def test_unsupported_file(client):
    r = client.post("/documents", files={"files": ("a.xlsx", b"abc", "x")})
    assert r.status_code == 415


def test_feedback_insights_and_scope(client):
    docs = client.post("/documents/samples").json()
    izin = next(d["id"] for d in docs if d["name"] == "izin-politikasi.md")
    a = client.post("/ask", json={"question": "Babalık izni kaç gün?", "mode": "extractive", "doc_ids": [izin]}).json()
    assert all(c["doc_id"] == izin for c in a["citations"])
    assert client.post("/feedback", json={"query_id": a["query_id"], "value": -1}).status_code == 204
    assert client.post("/feedback", json={"query_id": 9999, "value": 1}).status_code == 404
    ins = client.get("/insights").json()
    assert ins["total"] == 1 and ins["feedback_down"] == 1
    hits = client.get("/search", params={"q": "parola", "docs": str(izin)}).json()
    assert all(h["citation"]["doc_id"] == izin for h in hits)
    assert client.delete("/insights").status_code == 204
    assert client.get("/insights").json()["total"] == 0
