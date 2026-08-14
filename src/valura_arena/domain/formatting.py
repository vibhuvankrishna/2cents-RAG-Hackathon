"""Decimal formatting helpers."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def D(x) -> Decimal:
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def fmt_money(x: Decimal) -> str:
    return str(D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def fmt_pct(x: Decimal) -> str:
    return str(D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def fmt_qty(x: Decimal) -> str:
    # Keep up to 4 dp, strip trailing zeros carefully for exact match cases
    q = D(x).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    s = format(q, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
        # practice often keeps 4 dp for qty like 2.9849
        # re-check: 2.9849 should stay; if exact .0000 -> int
    # Prefer 4dp when non-integer
    if D(x) != D(x).to_integral_value():
        return str(D(x).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    return str(int(D(x)))


def try_dec(s) -> Decimal | None:
    try:
        return D(s)
    except (InvalidOperation, ValueError, TypeError):
        return None
