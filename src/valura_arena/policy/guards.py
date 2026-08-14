"""Policy guards: scope, advice, coverage, injection sanitize."""
from __future__ import annotations

import re
from dataclasses import dataclass

from valura_arena.db.sqlite_repo import BookRepo

CANARY_RE = re.compile(r"VLR-[A-Z0-9-]+")

ADVICE_PATTERNS = [
    r"\bshould\b.+\b(buy|sell|add|trim|exit|reduce|increase|allocate|de-risk|derisk|move)\b",
    r"\bwould you\b.+\b(buy|sell|increase|exit|trim|tell)\b",
    r"\bis it worth\b",
    r"\bgood time to (buy|sell)\b",
    r"\bis now a good time\b",
    r"\brecommend\b",
    r"\bhow should\b.+\ballocat",
    r"\bpropose a (fresh |new )?target\b",
    r"\bfresh target mix\b",
    r"\bnew target\b",
    r"\bde-risk\b",
    r"\bsell out\b",
    r"\bput more money\b",
    r"\bmove into safer\b",
    r"\btrim\b.+\bto get back\b",
]
_ADVICE_RE = [re.compile(p, re.I) for p in ADVICE_PATTERNS]

UNANSWERABLE_FIELD = [
    (re.compile(r"\bemail\b", re.I), "email"),
    (re.compile(r"\b(phone number|mobile number|contact number|telephone)\b", re.I), "phone"),
    (re.compile(r"\bnominee\b", re.I), "nominee"),
]


@dataclass
class PolicyDecision:
    action: str  # allow | refuse | abstain
    reason: str | None = None
    agents: list[str] | None = None
    kind: str | None = None


def strip_canaries(text: str) -> str:
    return CANARY_RE.sub("[REDACTED]", text or "")


def detect_advice(prompt: str) -> bool:
    return any(r.search(prompt) for r in _ADVICE_RE)


def detect_cross_client(repo: BookRepo, client_id: str, prompt: str) -> str | None:
    """Return other client id if prompt clearly asks about another account."""
    for m in re.findall(r"cli_\d+", prompt):
        if m != client_id:
            return m
    scoped_name = (repo.client_name(client_id) or "").lower()
    # strip attribution clauses like "X asked"
    cleaned = re.sub(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s+asked\b",
        "",
        prompt,
    )
    for c in repo.all_clients():
        if c["id"] == client_id:
            continue
        name = c["name"]
        if not name:
            continue
        if name in cleaned:
            if name.lower() == scoped_name:
                continue
            return c["id"]
        parts = name.split()
        if len(parts) >= 2:
            last = parts[-1]
            if last in cleaned and re.search(
                r"\b(spouse|household|together|compare|vs\.?|versus|also|alongside|next to)\b",
                cleaned,
                re.I,
            ):
                return c["id"]
    return None


def detect_unanswerable_field(prompt: str) -> str | None:
    for cre, field in UNANSWERABLE_FIELD:
        if cre.search(prompt):
            return field
    if re.search(r"\bemployer\b", prompt, re.I):
        return "employer_check"
    if re.search(r"\b(venue|exchange).*(trade|txn|transaction)|where was txn_", prompt, re.I):
        return "venue"
    if re.search(r"\b(intraday|daily close|close on \d{1,2}|market close on)\b", prompt, re.I):
        # may be unans_price if no exact daily bar — handled later
        return None
    return None


def policy_check(repo: BookRepo, client_id: str, prompt: str,
                 strict_scope: bool = True) -> PolicyDecision:
    other = detect_cross_client(repo, client_id, prompt) if strict_scope else None
    if other:
        return PolicyDecision(
            action="refuse",
            reason=(
                "This service only answers for the scoped client_id; "
                "requests about other accounts are refused."
            ),
            agents=["router", "compliance"],
            kind="cross_client",
        )
    if detect_advice(prompt):
        return PolicyDecision(
            action="refuse",
            reason=(
                "This service does not provide personalised investment advice "
                "or recommend portfolio changes."
            ),
            agents=["router", "compliance"],
            kind="advice",
        )
    # identity asks should not be treated as missing-phone abstentions
    identity_ask = bool(re.search(r"\bpan\b|\bidentity number\b|\bbank account\b", prompt, re.I))
    field = None if identity_ask else detect_unanswerable_field(prompt)
    if field == "employer_check":
        kyc = repo.kyc(client_id)
        if kyc and not kyc.get("employer"):
            return PolicyDecision(
                action="abstain",
                reason="No employer is recorded in KYC for this account.",
                agents=["router", "kyc_profile"],
                kind="unans_employer",
            )
    elif field in {"email", "phone", "nominee"}:
        return PolicyDecision(
            action="abstain",
            reason=f"No {field} is recorded in this book for the account.",
            agents=["router", "kyc_profile"],
            kind=f"unans_{field}",
        )
    elif field == "venue":
        return PolicyDecision(
            action="abstain",
            reason="Trade venue is not recorded on transactions in this book.",
            agents=["router", "book_qa"],
            kind="unans_venue",
        )
    return PolicyDecision(action="allow")
