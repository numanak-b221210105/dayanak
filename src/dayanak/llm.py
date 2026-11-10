"""OpenAI uyumlu LLM ve embedding istemcisi (OpenAI, Gemini, Groq, Ollama...).

Bağlantı yoksa istisna fırlatmak yerine None döndüren yardımcılar sunar;
böylece uygulama LLM olmadan da (anahtar kelime araması + alıntı tabanlı
cevap) çalışmaya devam eder.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import Settings

_cache: dict[str, tuple[float, bool]] = {}


def _client(s: Settings) -> Any:
    from openai import OpenAI

    return OpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        timeout=httpx.Timeout(120, connect=3),
        max_retries=1,
    )


def reachable(s: Settings, ttl: float = 20) -> bool:
    """LLM sunucusu ayakta mı? Sonuç kısa süre önbelleğe alınır."""
    now = time.monotonic()
    hit = _cache.get(s.llm_base_url)
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        httpx.get(f"{s.llm_base_url}/models", timeout=1.5)
        ok = True
    except httpx.HTTPError:
        ok = False
    _cache[s.llm_base_url] = (now, ok)
    return ok


def embed(s: Settings, texts: list[str]) -> list[list[float]] | None:
    if not texts or not reachable(s):
        return None
    try:
        res = _client(s).embeddings.create(model=s.embed_model, input=texts)
        return [d.embedding for d in res.data]
    except Exception:  # noqa: BLE001 - embedding modeli yoksa anahtar kelime aramasıyla devam
        return None


def chat(s: Settings, system: str, user: str, client: Any | None = None) -> str:
    res = (client or _client(s)).chat.completions.create(
        model=s.llm_model,
        temperature=0,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return res.choices[0].message.content or ""
