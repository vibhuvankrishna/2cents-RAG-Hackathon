"""PII masking."""
from __future__ import annotations


def mask_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw)
    if len(s) <= 4:
        return "****" + s
    return "****" + s[-4:]
