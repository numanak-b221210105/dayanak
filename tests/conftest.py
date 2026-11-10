from pathlib import Path
from types import SimpleNamespace

import pytest

from dayanak.config import Settings
from dayanak.engine import Engine

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def cfg(tmp_path: Path) -> Settings:
    # Kapalı bir port: testler hiçbir zaman gerçek bir LLM'e bağlanmaz
    return Settings(
        data_dir=tmp_path,
        llm_base_url="http://127.0.0.1:9/v1",
        llm_api_key="x",
        llm_model="test-model",
        embed_model="test-embed",
    )


class FakeLLM:
    """Sabit cevap döndüren, OpenAI uyumlu sahte istemci."""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


@pytest.fixture
def engine(tmp_path):
    eng = Engine(cfg(tmp_path))
    for f in sorted(SAMPLES.glob("*.md")):
        eng.add(f.name, f.read_bytes(), embed=False)
    return eng


@pytest.fixture
def engine_with_llm(tmp_path):
    def make(reply: str) -> Engine:
        eng = Engine(cfg(tmp_path), llm_client=FakeLLM(reply))
        for f in sorted(SAMPLES.glob("*.md")):
            eng.add(f.name, f.read_bytes(), embed=False)
        return eng

    return make
