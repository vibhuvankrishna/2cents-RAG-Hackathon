"""Citation helpers."""
from __future__ import annotations

CONTAINER_THRESHOLD = 6


def finalize_citations(ids: list[str], client_id: str | None = None) -> list[str]:
    # unique preserve order
    seen = set()
    out = []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    if client_id and len(out) > CONTAINER_THRESHOLD:
        return [client_id]
    return out
