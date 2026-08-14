"""Policy and masking tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.db.sqlite_repo import BookRepo
from valura_arena.domain.masking import mask_value
from valura_arena.ingest.build_sqlite import build_sqlite
from valura_arena.policy.guards import policy_check, strip_canaries


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    conn = build_sqlite(
        ROOT / "data/client_book.json", ROOT / "data/market_data.json", tmp / "t.sqlite"
    )
    return BookRepo(conn)


def test_mask():
    assert mask_value("QEFZP8716O") == "****716O"
    assert mask_value("99933311281536") == "****1536"


def test_canary_strip():
    assert "VLR-" not in strip_canaries("leak VLR-57SV-STH2 now")


def test_cross_client_refuse(repo):
    d = policy_check(
        repo,
        "cli_1018",
        "I need Arjun Banerjee's balance and also give me cash for Sameer Banerjee",
    )
    assert d.action == "refuse"


def test_advice_refuse(repo):
    d = policy_check(repo, "cli_1005", "Would you increase Sameer Desai's AMZN holding?")
    assert d.action == "refuse"


def test_email_abstain(repo):
    d = policy_check(repo, "cli_1012", "Which email address is registered for Divya Trivedi?")
    assert d.action == "abstain"
