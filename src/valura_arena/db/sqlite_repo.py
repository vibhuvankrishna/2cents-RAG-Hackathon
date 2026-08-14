"""SQLite repository for book/market queries."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from valura_arena.domain.formatting import D, fmt_money, fmt_pct, fmt_qty
from valura_arena.domain.citations import finalize_citations
from valura_arena.domain.masking import mask_value


class BookRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def as_of(self) -> str:
        return self.meta("book_as_of") or "2026-07-31"

    def client_name(self, client_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT name FROM clients WHERE id=?", (client_id,)
        ).fetchone()
        return row["name"] if row else None

    def all_clients(self) -> list[dict[str, str]]:
        rows = self.conn.execute("SELECT id, name FROM clients").fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    def covered_symbols(self) -> set[str]:
        rows = self.conn.execute("SELECT symbol FROM covered_symbols").fetchall()
        return {r["symbol"] for r in rows}

    def is_covered(self, symbol: str) -> bool:
        return symbol.upper() in {s.upper() for s in self.covered_symbols()}

    # --- cash / qty --------------------------------------------------------
    def cash_balance(self, client_id: str, through: str | None = None) -> tuple[Decimal, list[str]]:
        through = through or self.as_of()
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE client_id=? AND date<=? ORDER BY date, id",
            (client_id, through),
        ).fetchall()
        bal = Decimal("0")
        cites: list[str] = []
        for t in rows:
            typ = t["type"]
            cites.append(t["id"])
            if typ == "deposit":
                bal += D(t["amount_usd"])
            elif typ == "withdrawal":
                bal -= D(t["amount_usd"])
            elif typ == "buy":
                bal -= D(t["net_usd"])
            elif typ == "sell":
                bal += D(t["net_usd"])
            elif typ == "dividend":
                bal += D(t["net_usd"])
            elif typ == "fee":
                bal -= D(t["amount_usd"])
        return bal, finalize_citations(cites, client_id)

    def quantity(self, client_id: str, symbol: str, through: str | None = None) -> tuple[Decimal, list[str]]:
        through = through or self.as_of()
        rows = self.conn.execute(
            """SELECT * FROM transactions WHERE client_id=? AND symbol=? AND date<=?
               AND type IN ('buy','sell') ORDER BY date, id""",
            (client_id, symbol, through),
        ).fetchall()
        q = Decimal("0")
        cites: list[str] = []
        for t in rows:
            cites.append(t["id"])
            if t["type"] == "buy":
                q += D(t["quantity"])
            else:
                q -= D(t["quantity"])
        return q, finalize_citations(cites, client_id)

    def snapshot_qty(self, client_id: str, symbol: str) -> tuple[Decimal | None, str | None]:
        row = self.conn.execute(
            "SELECT id, quantity FROM positions_snapshot WHERE client_id=? AND symbol=?",
            (client_id, symbol),
        ).fetchone()
        if not row:
            return None, None
        return D(row["quantity"]), row["id"]

    def largest_deposit(self, client_id: str) -> tuple[Decimal | None, list[str]]:
        row = self.conn.execute(
            """SELECT id, amount_usd FROM transactions
               WHERE client_id=? AND type='deposit'
               ORDER BY CAST(amount_usd AS REAL) DESC, id LIMIT 1""",
            (client_id,),
        ).fetchone()
        if not row:
            return None, []
        return D(row["amount_usd"]), [row["id"]]

    def dividend_year(self, client_id: str, symbol: str, year: int) -> tuple[Decimal, list[str]]:
        rows = self.conn.execute(
            """SELECT id, net_usd FROM transactions
               WHERE client_id=? AND type='dividend' AND symbol=?
               AND date >= ? AND date <= ?""",
            (client_id, symbol, f"{year}-01-01", f"{year}-12-31"),
        ).fetchall()
        total = sum((D(r["net_usd"]) for r in rows), Decimal("0"))
        cites = [r["id"] for r in rows]
        return total, finalize_citations(cites, client_id)

    def first_buy(self, client_id: str, symbol: str) -> tuple[str | None, list[str]]:
        row = self.conn.execute(
            """SELECT id, date FROM transactions
               WHERE client_id=? AND type='buy' AND symbol=?
               ORDER BY date, id LIMIT 1""",
            (client_id, symbol),
        ).fetchone()
        if not row:
            return None, []
        return row["date"], [row["id"]]

    def count_trades(self, client_id: str, typ: str, year: int | None = None,
                     month: int | None = None, symbol: str | None = None) -> tuple[int, list[str]]:
        sql = "SELECT id FROM transactions WHERE client_id=? AND type=?"
        args: list[Any] = [client_id, typ]
        if symbol:
            sql += " AND symbol=?"
            args.append(symbol)
        if year and month:
            start = f"{year:04d}-{month:02d}-01"
            if month == 12:
                end = f"{year:04d}-12-31"
            else:
                end = f"{year:04d}-{month+1:02d}-01"
                sql_end = " AND date >= ? AND date < ?"
                rows = self.conn.execute(
                    sql + sql_end, (*args, start, end)
                ).fetchall()
                return len(rows), finalize_citations([r["id"] for r in rows], client_id)
            rows = self.conn.execute(
                sql + " AND date >= ? AND date <= ?", (*args, start, end)
            ).fetchall()
            return len(rows), finalize_citations([r["id"] for r in rows], client_id)
        if year:
            rows = self.conn.execute(
                sql + " AND date >= ? AND date <= ?",
                (*args, f"{year}-01-01", f"{year}-12-31"),
            ).fetchall()
            return len(rows), finalize_citations([r["id"] for r in rows], client_id)
        rows = self.conn.execute(sql, args).fetchall()
        return len(rows), finalize_citations([r["id"] for r in rows], client_id)

    def deposits_window(self, client_id: str, start: str, end: str) -> tuple[Decimal, list[str]]:
        rows = self.conn.execute(
            """SELECT id, amount_usd FROM transactions
               WHERE client_id=? AND type='deposit' AND date>=? AND date<=?""",
            (client_id, start, end),
        ).fetchall()
        total = sum((D(r["amount_usd"]) for r in rows), Decimal("0"))
        return total, finalize_citations([r["id"] for r in rows], client_id)

    def deposits_year(self, client_id: str, year: int) -> tuple[Decimal, list[str]]:
        return self.deposits_window(client_id, f"{year}-01-01", f"{year}-12-31")

    def total_fees(self, client_id: str) -> tuple[Decimal, list[str]]:
        rows = self.conn.execute(
            "SELECT id, amount_usd FROM transactions WHERE client_id=? AND type='fee'",
            (client_id,),
        ).fetchall()
        total = sum((D(r["amount_usd"]) for r in rows), Decimal("0"))
        return total, finalize_citations([r["id"] for r in rows], client_id)

    def holdings_count_asof(self, client_id: str, asof: str) -> tuple[int, list[str]]:
        rows = self.conn.execute(
            """SELECT symbol FROM transactions
               WHERE client_id=? AND type IN ('buy','sell') AND date<=?""",
            (client_id, asof),
        ).fetchall()
        from collections import defaultdict
        qty: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        # need actual reconstruction
        txns = self.conn.execute(
            """SELECT * FROM transactions WHERE client_id=? AND type IN ('buy','sell')
               AND date<=? ORDER BY date, id""",
            (client_id, asof),
        ).fetchall()
        for t in txns:
            sym = t["symbol"]
            if t["type"] == "buy":
                qty[sym] += D(t["quantity"])
            else:
                qty[sym] -= D(t["quantity"])
        held = [s for s, q in qty.items() if q > 0]
        return len(held), finalize_citations([], client_id) or [client_id]

    def account_age_days(self, client_id: str) -> tuple[int | None, list[str]]:
        row = self.conn.execute(
            "SELECT id, opened FROM accounts WHERE client_id=? ORDER BY opened LIMIT 1",
            (client_id,),
        ).fetchone()
        if not row or not row["opened"]:
            return None, []
        from datetime import date
        opened = date.fromisoformat(row["opened"])
        asof = date.fromisoformat(self.as_of())
        return (asof - opened).days, [row["id"]]

    # --- KYC ---------------------------------------------------------------
    def kyc(self, client_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM kyc WHERE client_id=?", (client_id,)
        ).fetchone()
        return dict(row) if row else None

    def latest_review(self, client_id: str) -> dict | None:
        row = self.conn.execute(
            """SELECT * FROM suitability_reviews WHERE client_id=?
               ORDER BY date DESC, id DESC LIMIT 1""",
            (client_id,),
        ).fetchone()
        return dict(row) if row else None

    def notes(self, client_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE client_id=? ORDER BY date, id",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def txn(self, txn_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM transactions WHERE id=?", (txn_id,)
        ).fetchone()
        return dict(row) if row else None

    def memos(self, client_id: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT id, date, symbol, memo FROM transactions
               WHERE client_id=? AND memo IS NOT NULL AND memo != ''""",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- market ------------------------------------------------------------
    def price_on_or_before(self, symbol: str, day: str) -> tuple[str, str] | None:
        row = self.conn.execute(
            """SELECT date, close FROM prices WHERE symbol=? AND date<=?
               ORDER BY date DESC LIMIT 1""",
            (symbol, day),
        ).fetchone()
        if not row:
            return None
        return row["date"], row["close"]

    def exact_price(self, symbol: str, day: str) -> tuple[str, str] | None:
        row = self.conn.execute(
            "SELECT date, close FROM prices WHERE symbol=? AND date=?",
            (symbol, day),
        ).fetchone()
        if not row:
            return None
        return row["date"], row["close"]

    def market_return(self, symbol: str, start: str, end: str) -> tuple[Decimal, list[str]]:
        a = self.price_on_or_before(symbol, start)
        b = self.price_on_or_before(symbol, end)
        if not a or not b:
            raise ValueError("missing prices")
        ret = (D(b[1]) - D(a[1])) / D(a[1]) * Decimal("100")
        return ret, [symbol]

    def sector_exposure(self, client_id: str, sector: str) -> tuple[Decimal, list[str]]:
        positions = self.conn.execute(
            "SELECT * FROM positions_snapshot WHERE client_id=?", (client_id,)
        ).fetchall()
        if not positions:
            return Decimal("0"), []
        total = sum((D(p["market_value_usd"]) for p in positions), Decimal("0"))
        cites = []
        sec_val = Decimal("0")
        for p in positions:
            inst = self.conn.execute(
                "SELECT sector FROM instruments WHERE symbol=?", (p["symbol"],)
            ).fetchone()
            if inst and inst["sector"] == sector:
                sec_val += D(p["market_value_usd"])
                cites.append(p["id"])
        if total == 0:
            return Decimal("0"), cites
        return (sec_val / total * Decimal("100")), cites

    def news_asof(self, symbol: str, asof: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM news WHERE symbol=? AND date<=? ORDER BY date, id",
            (symbol, asof),
        ).fetchall()
        return [dict(r) for r in rows]

    def drift(self, client_id: str, symbol: str) -> tuple[Decimal, list[str]]:
        rev = self.latest_review(client_id)
        if not rev:
            raise ValueError("no review")
        target_row = self.conn.execute(
            "SELECT pct FROM target_allocations WHERE review_id=? AND symbol=?",
            (rev["id"], symbol),
        ).fetchone()
        if not target_row:
            raise ValueError("no target")
        target = D(target_row["pct"])
        positions = self.conn.execute(
            "SELECT * FROM positions_snapshot WHERE client_id=?", (client_id,)
        ).fetchall()
        total = sum((D(p["market_value_usd"]) for p in positions), Decimal("0"))
        pos = next((p for p in positions if p["symbol"] == symbol), None)
        if not pos or total == 0:
            actual = Decimal("0")
            cites = [rev["id"]]
        else:
            actual = D(pos["market_value_usd"]) / total * Decimal("100")
            cites = [pos["id"], rev["id"]]
        return actual - target, cites

    def instrument(self, symbol: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM instruments WHERE symbol=?", (symbol,)
        ).fetchone()
        return dict(row) if row else None
