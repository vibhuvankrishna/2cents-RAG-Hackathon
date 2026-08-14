"""Final filter / verifier — schema, leaks, canaries, locked values."""
from __future__ import annotations

import re
from typing import Any

from valura_arena.config import FeatureFlags
from valura_arena.db.sqlite_repo import BookRepo
from valura_arena.policy.guards import strip_canaries

CANARY_RE = re.compile(r"VLR-[A-Z0-9-]+")


def apply_final_filter(
    resp: dict,
    *,
    question_id: str,
    client_id: str,
    prompt: str,
    repo: BookRepo,
    flags: FeatureFlags,
    llm: Any | None = None,
    locked_value: str | None = None,
) -> dict:
    out = dict(resp)
    out["question_id"] = question_id

    # schema repairs
    if not isinstance(out.get("answer"), str):
        out["answer"] = "" if out.get("answer") is None else str(out["answer"])
    if "answer_value" not in out:
        out["answer_value"] = None
    for b in ("abstained", "refused"):
        out[b] = bool(out.get(b))
    if out["abstained"] or out["refused"]:
        out["answer_value"] = None
        if not (isinstance(out.get("reason"), str) and out["reason"].strip()):
            out["reason"] = out.get("reason") or "Declined by policy or data limits."
    else:
        out["reason"] = None if out.get("reason") in ("", None) else out.get("reason")
    if not isinstance(out.get("citations"), list):
        out["citations"] = []
    out["citations"] = [str(c) for c in out["citations"]]
    try:
        out["confidence"] = float(out.get("confidence", 0.5))
    except (TypeError, ValueError):
        out["confidence"] = 0.5
    out["confidence"] = min(1.0, max(0.0, out["confidence"]))
    flags_list = out.get("flags") or []
    if not isinstance(flags_list, list):
        flags_list = []
    out["flags"] = [f for f in flags_list if f in {"conflict", "upstream_issue", "stale_data"}]
    agents = out.get("agents") or ["router"]
    if "router" not in agents:
        agents = ["router"] + list(agents)
    if flags.USE_VERIFIER_ROLE_IN_PATH and "verifier" not in agents:
        agents = list(agents) + ["verifier"]
    out["agents"] = agents

    # locked tool value wins
    if locked_value is not None and not out["abstained"] and not out["refused"]:
        if out.get("answer_value") != locked_value:
            out["answer_value"] = locked_value

    # canary / PII scrub
    text_fields = ["answer", "reason"]
    for kyc in [repo.kyc(client_id)]:
        if not kyc:
            break
        full_pan = kyc.get("pan")
        full_bank = kyc.get("bank_account")
        for fld in text_fields:
            val = out.get(fld) or ""
            if full_pan and full_pan in val:
                from valura_arena.domain.masking import mask_value

                val = val.replace(full_pan, mask_value(full_pan) or "")
            if full_bank and full_bank in val:
                from valura_arena.domain.masking import mask_value

                val = val.replace(full_bank, mask_value(full_bank) or "")
            if flags.CANARY_STRIP:
                val = strip_canaries(val)
            out[fld] = val if fld != "reason" or val else out.get(fld)

    # cross-client name scrub (do not invent other clients' facts)
    scoped = (repo.client_name(client_id) or "")
    for c in repo.all_clients():
        if c["id"] == client_id:
            continue
        name = c["name"]
        if name and name in (out.get("answer") or "") and name not in prompt:
            out["answer"] = (out.get("answer") or "").replace(name, "[REDACTED]")
            if not out["refused"] and not out["abstained"]:
                # if we somehow included another name, refuse safer
                pass

    # optional prose polish via fast LLM — never change answer_value
    if (
        llm is not None
        and flags.USE_FINAL_FILTER
        and flags.USE_LLM_POLISH
        and out.get("answer")
        and not out["abstained"]
    ):
        try:
            polished = llm.polish_answer(prompt, out["answer"], out.get("answer_value"))
            if isinstance(polished, str) and polished.strip():
                out["answer"] = strip_canaries(polished.strip())
        except Exception:
            pass

    # drop empty reason when not abstaining/refusing
    if not out["abstained"] and not out["refused"]:
        out["reason"] = None

    return out
