"""Unit tests for cash / as-of against practice key."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.config import Settings
from valura_arena.db.sqlite_repo import BookRepo
from valura_arena.domain.formatting import fmt_money, fmt_qty
from valura_arena.ingest.build_sqlite import build_sqlite


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    db = tmp / "t.sqlite"
    conn = build_sqlite(ROOT / "data/client_book.json", ROOT / "data/market_data.json", db)
    return BookRepo(conn)


@pytest.fixture(scope="module")
def key():
    return json.loads((ROOT / "harness/practice_key.json").read_text(encoding="utf-8"))


def test_cash_balance(repo, key):
    q = key["questions"]["q_001"]
    bal, _ = repo.cash_balance(q["client_id"])
    assert fmt_money(bal) == q["expected"]["value"]


def test_cash_asof(repo, key):
    q = key["questions"]["q_009"]
    bal, _ = repo.cash_balance(q["client_id"], q["params"]["asof"])
    assert fmt_money(bal) == q["expected"]["value"]


def test_qty(repo, key):
    q = key["questions"]["q_007"]
    qty, _ = repo.quantity(q["client_id"], q["params"]["symbol"])
    assert fmt_qty(qty) == q["expected"]["value"]


def test_market_return(repo, key):
    q = key["questions"]["q_056"]
    p = q["params"]
    ret, _ = repo.market_return(p["symbol"], p["from"], p["to"])
    from valura_arena.domain.formatting import fmt_pct

    assert fmt_pct(ret) == q["expected"]["value"]


def test_drift(repo, key):
    q = key["questions"]["q_066"]
    p = q["params"]
    d, cites = repo.drift(p["client_id"], p["symbol"])
    from valura_arena.domain.formatting import fmt_pct

    assert fmt_pct(d) == q["expected"]["value"]
    assert set(q["expected"]["citations"]).issubset(set(cites))
