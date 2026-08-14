"""Heuristic intent classification from natural-language prompts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
YEAR_RE = re.compile(r"\b(20\d{2})\b")
MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b",
    re.I,
)
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

KNOWN = {
    "AAPL", "AMD", "AMZN", "GOOG", "INTC", "JPM", "KO", "META", "MSFT", "NFLX",
    "NVDA", "QQQ", "TSLA", "VOO", "PFE", "WMT", "XOM", "DIS", "IBM", "NKE",
}

STOP = {
    "USD", "INR", "KYC", "PAN", "LRS", "IFSC", "THE", "AND", "FOR", "WHAT", "HOW",
    "WHO", "WHOSE", "WHEN", "WHERE", "WHICH", "GIVE", "TELL", "FIND", "LOOK", "WORK",
    "WITH", "FROM", "INTO", "THAT", "THIS", "THEY", "THEM", "HAVE", "HAS", "HAD",
    "DOES", "DID", "MAKE", "MADE", "MORE", "MUCH", "MANY", "ALSO", "ONLY", "JUST",
}


@dataclass
class Intent:
    kind: str
    roles: list[str] = field(default_factory=lambda: ["router", "book_qa"])
    symbol: str | None = None
    sector: str | None = None
    asof: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    year: int | None = None
    month: int | None = None
    txn_id: str | None = None
    needs_deep: bool = False
    no_deep: bool = False
    free_text: bool = False


def _symbols(prompt: str) -> list[str]:
    found = []
    for m in re.findall(r"\b([A-Za-z]{2,5})\b", prompt):
        u = m.upper()
        if u in STOP:
            continue
        if u in KNOWN or (m.isupper() and len(m) <= 5):
            found.append(u)
    return list(dict.fromkeys(found))


def _parse_mdy(s: str) -> str | None:
    m = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",
        s,
        re.I,
    )
    if not m:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def _named_dates(prompt: str) -> list[str]:
    all_d = re.findall(
        r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}",
        prompt,
        re.I,
    )
    out = []
    for d in all_d:
        p = _parse_mdy(d)
        if p:
            out.append(p)
    return out


def detect_advice_local(pl: str) -> bool:
    return bool(
        re.search(
            r"should|worth|recommend|propose a|fresh target|good time|de-risk|"
            r"trim .+ to get|sell out|move into safer|put more money",
            pl,
        )
    )


def classify(prompt: str) -> Intent:
    p = prompt
    pl = prompt.lower()
    syms = _symbols(prompt)
    sym = syms[0] if syms else None
    dates = DATE_RE.findall(prompt) + _named_dates(prompt)
    # unique preserve order
    seen = set()
    dates = [d for d in dates if not (d in seen or seen.add(d))]
    years = [int(y) for y in YEAR_RE.findall(prompt)]
    month = None
    year = None
    mm = MONTH_RE.search(prompt)
    if mm:
        month = MONTHS[mm.group(1).lower()]
        year = int(mm.group(2))
    txn_m = re.search(r"(txn_\d+)", prompt)
    txn_id = txn_m.group(1) if txn_m else None

    # advice first (before book heuristics)
    if detect_advice_local(pl) and re.search(
        r"\b(buy|sell|allocat|safer|de-risk|trim|increase|exit|fund|money into)\b", pl
    ):
        if re.search(r"\b(drift|mandate|overweight|underweight|target mix)\b", pl):
            return Intent("rebalance_advice", ["router", "compliance"], symbol=sym)
        return Intent("advice", ["router", "compliance"], symbol=sym)

    # multi-agent combos
    if re.search(r"\bpan\b", pl) and re.search(r"\b(first|bought|buy|purchase)\b", pl):
        return Intent("multi_pan_firstbuy", ["router", "kyc_profile", "book_qa"], symbol=sym or "AAPL")
    if re.search(r"\brisk profile\b", pl) and re.search(r"\b(holding|holdings|distinct)\b", pl):
        return Intent("multi_kyc_holdings", ["router", "kyc_profile", "book_qa"])
    if re.search(r"\bnotes?\b", pl) and re.search(r"\bkyc\b", pl):
        return Intent("multi_notes_kyc", ["router", "notes_desk", "kyc_profile"], needs_deep=True)

    # conflicts / KYC standing
    if re.search(r"\brisk (profile|category|classification)\b", pl):
        return Intent("conflict_or_risk", ["router", "kyc_profile"])
    if re.search(r"\bkyc\b", pl) and re.search(
        r"\b(complete|standing|status|position|good standing|verified)\b", pl
    ):
        return Intent("conflict_or_kyc_status", ["router", "kyc_profile"])

    # PII
    if re.search(r"\bpan\b", pl) or re.search(r"\bidentity number\b", pl) or re.search(
        r"\bpermanent account\b", pl
    ):
        return Intent("pii_pan", ["router", "kyc_profile"])
    if re.search(r"\b(account number|bank account|final four digits|last four)\b", pl):
        return Intent("pii_bank", ["router", "kyc_profile"])

    # employer
    if re.search(r"\bemployer\b|\bwhich company\b", pl):
        return Intent("employer", ["router", "kyc_profile"], free_text=True)

    # notes / memos
    if re.search(r"\bnotes?\b|\brelationship notes\b|\bfile carry\b|\bstill pending\b", pl):
        if re.search(r"\bcash\b|\bbalance\b", pl):
            return Intent("multi_notes_cash", ["router", "notes_desk", "book_qa"], needs_deep=True)
        return Intent("notes_summary", ["router", "notes_desk"], needs_deep=True)
    if re.search(r"\bmemo\b|recorded against .+ transaction|txn_", pl):
        return Intent("txn_memo", ["router", "notes_desk"], txn_id=txn_id, needs_deep=True)

    # unsourced sector / which sector
    if re.search(r"\bwhich sector\b|\bwhat sector\b|\bfile .+ under\b|\bsector does\b", pl):
        return Intent("unsourced_sector", ["router", "market_desk"], symbol=sym)

    # sector exposure
    if re.search(r"\bsector\b|\bweight\b.*\b(portfolio|communication|technology)\b", pl) or re.search(
        r"\bcommunication services\b|\binformation technology\b", pl
    ):
        sector = None
        for s in (
            "Communication Services",
            "Information Technology",
            "Consumer Discretionary",
            "Consumer Staples",
            "Financials",
            "Health Care",
            "Energy",
        ):
            if s.lower() in pl:
                sector = s
                break
        if not sector and "communication" in pl:
            sector = "Communication Services"
        return Intent("sector_exposure", ["router", "market_desk", "book_qa"], sector=sector, symbol=sym)

    # news
    if re.search(r"\bnews\b|\bheadlines?\b|\bstories\b|\bfeed\b|\bcoverage\b", pl):
        asof = dates[0] if dates else None
        if not asof:
            nd = _named_dates(prompt)
            asof = nd[0] if nd else None
        return Intent("news_summary", ["router", "market_desk"], symbol=sym, asof=asof, needs_deep=True)

    # market return / price
    if re.search(
        r"\b(percentage move|gain or lose|return|moved from|performance|percentage points)\b", pl
    ) or re.search(r"\bclose on\b|\bmarket close\b", pl):
        if re.search(r"\bmarket close on\b|\bclose on\b", pl) and dates:
            return Intent("unans_or_price", ["router", "market_desk"], symbol=sym, asof=dates[0])
        if len(dates) >= 2:
            return Intent(
                "market_return",
                ["router", "market_desk"],
                symbol=sym,
                date_from=dates[0],
                date_to=dates[1],
            )
        if re.search(r"\bperformance\b|\bread on\b", pl) and sym:
            return Intent("unsourced_or_return", ["router", "market_desk"], symbol=sym)

    # drift
    if re.search(
        r"\b(drift|far off|gap between|differ from|weighting differ|overweight|underweight|mandate)\b",
        pl,
    ) or re.search(r"\bagreed target\b", pl):
        if detect_advice_local(pl):
            return Intent("rebalance_advice", ["router", "compliance"], symbol=sym)
        return Intent("rebalance_drift", ["router", "market_desk", "book_qa"], symbol=sym)

    # as-of
    if re.search(r"\bas at\b|\bas of\b|\bstood on\b|\bas it stood\b", pl):
        asof = dates[0] if dates else None
        if re.search(r"\bcash\b|\bbalance\b", pl):
            return Intent("cash_asof", ["router", "book_qa"], asof=asof, no_deep=True)
        if re.search(r"\b(share|holding|quantity|shares)\b", pl) or sym:
            return Intent("qty_asof", ["router", "book_qa"], symbol=sym, asof=asof, no_deep=True)
        if re.search(r"\bhow many (separate )?stocks\b|\bdifferent symbols\b", pl):
            return Intent("holdings_count_asof", ["router", "book_qa"], asof=asof)

    if re.search(r"\bcash\b|\bbalance\b", pl):
        return Intent("cash_balance", ["router", "book_qa"], no_deep=True)

    if re.search(
        r"\blargest .+deposit\b|\bbiggest .+deposit\b|\bbiggest one-off\b|\bmoney .+paid in\b|"
        r"\bwhat was the largest\b|\bfunding amount\b",
        pl,
    ):
        return Intent("largest_deposit", ["router", "book_qa"], no_deep=True)

    if re.search(r"\bdividend", pl):
        y = year or (years[0] if years else None)
        return Intent("dividend_year", ["router", "book_qa"], symbol=sym, year=y)

    if re.search(
        r"\bfirst (buy|purchase)|started holding|earliest .+purchase|first \w+ purchase|purchase settle\b",
        pl,
    ) or re.search(r"\bon what date\b.+\bbuy\b", pl):
        return Intent("first_buy", ["router", "book_qa"], symbol=sym)

    if re.search(
        r"\bsell transaction|\bhow many times.+\bsell\b|\bsale transaction|\bdisposals?\b",
        pl,
    ):
        return Intent("sell_count_month", ["router", "book_qa"], symbol=sym, year=year, month=month)

    if re.search(r"\bhow many buys\b|\bbuy transaction|\bpurchases?\b|\bcount the buys\b|\bbuys? on\b", pl):
        if year and not month and re.search(r"\btotal\b|\bin total\b|\bseparate\b", pl):
            return Intent("buy_count_total", ["router", "book_qa"], symbol=sym)
        return Intent("buy_count_month", ["router", "book_qa"], symbol=sym, year=year, month=month)

    if re.search(r"\bplatform fees?\b|\bfees charged\b", pl):
        return Intent("whale_fees", ["router", "book_qa"])

    if re.search(r"\bbetween\b.+\band\b", pl) and re.search(
        r"\bdeposit|funded|funding|paid in\b", pl
    ):
        nd = dates if len(dates) >= 2 else _named_dates(prompt)
        if len(nd) >= 2:
            return Intent(
                "deposits_window",
                ["router", "book_qa"],
                date_from=nd[0],
                date_to=nd[1],
            )

    if re.search(r"\bdeposit.+\b(during|in|across)\b|\bfunding across\b|\bfunded between\b", pl):
        y = year or (years[0] if years else None)
        return Intent("deposits_year", ["router", "book_qa"], year=y)

    if re.search(
        r"\bhow many .{0,20}shares\b|\bshare count\b|\bholding in\b|\bquantity of\b|"
        r"\bcurrently hold\b|\bis holding\b|\bhow much \w+ .+ holding\b|\blook up how much\b|"
        r"\bposition size\b|\bhold(?:s|ing)?\b.*\b(aapl|msft|goog|amzn|amd)\b",
        pl,
    ):
        return Intent("position_qty", ["router", "book_qa"], symbol=sym, no_deep=True)

    if re.search(r"\bhow many days\b|\baccount age\b|\bbeen a client\b|\bage of\b.+\baccount\b", pl):
        return Intent("account_age", ["router", "book_qa"], no_deep=True)

    # drift / news late catch-alls
    if re.search(r"\btarget\b", pl) and re.search(r"\b(weight|allocation|mandate|over|under)\b", pl):
        return Intent("rebalance_drift", ["router", "market_desk", "book_qa"], symbol=sym)

    if re.search(r"\b(brief me|published by|predate|articles?|items that is)\b", pl) and sym:
        asof = dates[0] if dates else None
        return Intent("news_summary", ["router", "market_desk"], symbol=sym, asof=asof)

    return Intent("unknown", ["router", "book_qa"], symbol=sym)
