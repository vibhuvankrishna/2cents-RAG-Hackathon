#!/usr/bin/env python
"""Ingest local book/market into SQLite (+ chroma)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.config import Settings
from valura_arena.db.sqlite_repo import BookRepo
from valura_arena.db.vector_repo import VectorRepo, build_chroma_from_sqlite
from valura_arena.ingest.build_sqlite import build_sqlite


def main() -> None:
    s = Settings.from_env()
    conn = build_sqlite(s.book_path, s.market_path, s.sqlite_path)
    repo = BookRepo(conn)
    print(f"sqlite -> {s.sqlite_path} clients={len(repo.all_clients())}")
    if s.features.USE_CHROMA:
        v = VectorRepo(s.chroma_path, use_chroma=True)
        build_chroma_from_sqlite(repo, v)
        print(f"chroma -> {s.chroma_path}")


if __name__ == "__main__":
    main()
