"""Conflict detection tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.db.sqlite_repo import BookRepo
from valura_arena.domain.conflicts import risk_conflict, snapshot_conflict
from valura_arena.ingest.build_sqlite import build_sqlite


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    conn = build_sqlite(
        ROOT / "data/client_book.json", ROOT / "data/market_data.json", tmp / "t.sqlite"
    )
    return BookRepo(conn)


def test_risk_conflict(repo):
    c = risk_conflict(repo, "cli_1010")
    assert c is not None
    assert "kyc_1010" in c["citations"]


def test_snapshot_conflict(repo):
    c = snapshot_conflict(repo, "cli_1022", "AAPL")
    assert c is not None
    assert "pos_1022_AAPL" in c["citations"]
