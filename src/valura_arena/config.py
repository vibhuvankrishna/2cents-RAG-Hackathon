"""Configuration and feature flags."""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class FeatureFlags:
    USE_SQLITE: bool = True
    USE_CHROMA: bool = True
    USE_AGNO_TEAM: bool = True
    USE_FINAL_FILTER: bool = True
    USE_LLM_POLISH: bool = False
    USE_GATEWAY_HEARTBEAT: bool = True
    USE_DETERMINISTIC_FIRST: bool = True
    USE_DEEP_NOTES: bool = True
    USE_VERIFIER_ROLE_IN_PATH: bool = True
    STRICT_SCOPE_SCAN: bool = True
    CANARY_STRIP: bool = True
    BLACKOUT_DETERMINISTIC: bool = True
    CACHE_ANSWERS: bool = True
    USE_LOCAL_EMBEDDINGS: bool = False
    ALERT_WEBHOOK: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> "FeatureFlags":
        data: dict[str, Any] = {}
        cfg = path or Path(os.environ.get("FEATURES_PATH", ROOT / "features.yaml"))
        if cfg.exists():
            loaded = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            data.update({k: bool(v) for k, v in loaded.items()})
        ff = cls(**{f.name: data.get(f.name, getattr(cls, f.name))
                    for f in fields(cls)})
        for f in fields(cls):
            setattr(ff, f.name, _env_bool(f.name, getattr(ff, f.name)))
        return ff


@dataclass
class Settings:
    book_path: Path
    market_path: Path
    llm_base_url: str
    llm_api_key: str
    port: int
    sqlite_path: Path
    chroma_path: Path
    features: FeatureFlags
    alert_webhook_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        book = Path(os.environ.get("BOOK_PATH", ROOT / "data" / "client_book.json"))
        market = Path(os.environ.get("MARKET_PATH", ROOT / "data" / "market_data.json"))
        data_dir = Path(os.environ.get("DATA_DIR", ROOT / ".var"))
        data_dir.mkdir(parents=True, exist_ok=True)
        features = FeatureFlags.load()
        return cls(
            book_path=book,
            market_path=market,
            llm_base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8600/v1").rstrip("/"),
            llm_api_key=os.environ.get("LLM_API_KEY", "assessment"),
            port=int(os.environ.get("PORT", "8080")),
            sqlite_path=Path(os.environ.get("SQLITE_PATH", data_dir / "book.sqlite")),
            chroma_path=Path(os.environ.get("CHROMA_PATH", data_dir / "chroma")),
            features=features,
            alert_webhook_url=os.environ.get("ALERT_WEBHOOK_URL"),
        )
