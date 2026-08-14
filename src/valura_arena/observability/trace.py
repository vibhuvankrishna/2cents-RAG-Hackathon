"""Observability: traces and alerts."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx


class TraceLog:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.events: list[dict] = []

    def emit(self, kind: str, **payload: Any) -> None:
        ev = {"ts": time.time(), "kind": kind, **payload}
        self.events.append(ev)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev) + "\n")
        if kind.startswith("ALERT"):
            print(f"ALERT: {kind} {payload}", flush=True)

    def webhook(self, url: str | None, kind: str, **payload: Any) -> None:
        if not url:
            return
        try:
            httpx.post(url, json={"kind": kind, **payload}, timeout=3)
        except Exception:
            pass
