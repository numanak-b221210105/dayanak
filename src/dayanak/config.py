"""Ortam değişkenlerinden ayarlar. Hepsinin çalışan bir varsayılanı vardır."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    embed_model: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "dayanak.sqlite3"


def settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DAYANAK_DATA_DIR", "data")),
        llm_base_url=os.getenv("DAYANAK_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/"),
        llm_api_key=os.getenv("DAYANAK_LLM_API_KEY", "ollama"),
        llm_model=os.getenv("DAYANAK_LLM_MODEL", "qwen2.5:7b"),
        embed_model=os.getenv("DAYANAK_EMBED_MODEL", "bge-m3"),
    )
