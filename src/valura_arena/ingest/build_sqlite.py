"""Build SQLite DB from book + market JSON."""
from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from typing import Any

from valura_arena.ingest.load_json import load_json

SCHEMA = Path(__file__).with_name("sqlite_schema.sql").read_text(encoding="utf-8")


def build_sqlite(book_path: Path, market_path: Path, sqlite_path: Path) -> sqlite3.Connection:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        try:
            sqlite_path.unlink()
        except PermissionError:
            # Windows: previous connection still open — open unique path
            sqlite_path = sqlite_path.with_name(
                f"{sqlite_path.stem}_{os.getpid()}{sqlite_path.suffix}"
            )
    conn = sqlite3.connect(str(sqlite_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    book = load_json(book_path)
    market = load_json(market_path)
    _ingest_book(conn, book)
    _ingest_market(conn, market)
    conn.commit()
    return conn


def open_sqlite(sqlite_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(sqlite_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        (key, "" if value is None else str(value)),
    )


def _ingest_book(conn: sqlite3.Connection, book: dict) -> None:
    meta = book.get("meta") or {}
    for k, v in meta.items():
        if isinstance(v, (dict, list)):
            continue
        _meta(conn, f"book_{k}", v)
    for c in book["clients"]:
        cid = c["id"]
        conn.execute(
            "INSERT INTO clients(id, name) VALUES (?, ?)",
            (cid, c.get("name") or ""),
        )
        kyc = c.get("kyc") or {}
        emp = kyc.get("employment") or {}
        bank = kyc.get("bank_account") or {}
        conn.execute(
            """INSERT INTO kyc(
                id, client_id, pan, kyc_status, risk_profile, date_of_birth,
                address, annual_income_band, bank_name, bank_account, ifsc,
                employer, occupation
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                kyc.get("id") or f"kyc_{cid}",
                cid,
                kyc.get("pan"),
                kyc.get("kyc_status"),
                kyc.get("risk_profile"),
                kyc.get("date_of_birth"),
                kyc.get("address"),
                kyc.get("annual_income_band"),
                bank.get("bank"),
                bank.get("account_number"),
                bank.get("ifsc"),
                emp.get("employer"),
                emp.get("occupation"),
            ),
        )
        for a in c.get("accounts") or []:
            conn.execute(
                """INSERT INTO accounts(id, client_id, opened, broker_ref, base_currency)
                   VALUES (?,?,?,?,?)""",
                (a["id"], cid, a.get("opened"), a.get("broker_ref"), a.get("base_currency")),
            )
        for rev in c.get("suitability_reviews") or []:
            conn.execute(
                """INSERT INTO suitability_reviews(id, client_id, date, risk_profile, reviewer, outcome)
                   VALUES (?,?,?,?,?,?)""",
                (
                    rev["id"],
                    cid,
                    rev.get("date"),
                    rev.get("risk_profile"),
                    rev.get("reviewer"),
                    rev.get("outcome"),
                ),
            )
            for sym, pct in (rev.get("target_allocation_pct") or {}).items():
                conn.execute(
                    "INSERT INTO target_allocations(review_id, symbol, pct) VALUES (?,?,?)",
                    (rev["id"], sym, str(pct)),
                )
        for n in c.get("notes") or []:
            conn.execute(
                "INSERT INTO notes(id, client_id, date, author, text) VALUES (?,?,?,?,?)",
                (n["id"], cid, n.get("date"), n.get("author"), n.get("text")),
            )
        for t in c.get("transactions") or []:
            conn.execute(
                """INSERT INTO transactions(
                    id, client_id, date, type, symbol, quantity, price_usd, gross_usd,
                    fees_usd, net_usd, amount_usd, amount_inr, fx_rate, lrs_ref,
                    description, destination, withholding_tax_usd, memo
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    t["id"],
                    cid,
                    t["date"],
                    t["type"],
                    t.get("symbol"),
                    t.get("quantity"),
                    t.get("price_usd"),
                    t.get("gross_usd"),
                    t.get("fees_usd"),
                    t.get("net_usd"),
                    t.get("amount_usd"),
                    t.get("amount_inr"),
                    t.get("fx_rate"),
                    t.get("lrs_ref"),
                    t.get("description"),
                    t.get("destination"),
                    t.get("withholding_tax_usd"),
                    t.get("memo"),
                ),
            )
        for p in c.get("positions_snapshot") or []:
            conn.execute(
                """INSERT INTO positions_snapshot(
                    id, client_id, symbol, quantity, avg_cost_usd, market_value_usd
                ) VALUES (?,?,?,?,?,?)""",
                (
                    p["id"],
                    cid,
                    p["symbol"],
                    p.get("quantity"),
                    p.get("avg_cost_usd"),
                    p.get("market_value_usd"),
                ),
            )


def _ingest_market(conn: sqlite3.Connection, market: dict) -> None:
    meta = market.get("meta") or {}
    for k, v in meta.items():
        if k == "covered_symbols":
            continue
        if isinstance(v, (dict, list)):
            continue
        _meta(conn, f"market_{k}", v)
    for sym in meta.get("covered_symbols") or []:
        conn.execute("INSERT OR IGNORE INTO covered_symbols(symbol) VALUES (?)", (sym,))
    for inst in market.get("instruments") or []:
        conn.execute(
            """INSERT INTO instruments(symbol, sector, industry, currency, listed_on)
               VALUES (?,?,?,?,?)""",
            (
                inst["symbol"],
                inst.get("sector"),
                inst.get("industry"),
                inst.get("currency"),
                inst.get("listed_on"),
            ),
        )
    for sym, series in (market.get("prices") or {}).items():
        for row in series:
            conn.execute(
                "INSERT INTO prices(symbol, date, close) VALUES (?,?,?)",
                (sym, row["date"], row["close"]),
            )
    for n in market.get("news") or []:
        conn.execute(
            """INSERT INTO news(id, date, symbol, headline, body, source)
               VALUES (?,?,?,?,?,?)""",
            (
                n["id"],
                n.get("date"),
                n.get("symbol"),
                n.get("headline"),
                n.get("body"),
                n.get("source"),
            ),
        )
