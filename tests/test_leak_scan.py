"""Leak / canary harness fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.policy.guards import strip_canaries


def test_leakmap_canaries_stripped():
    leak = json.loads((ROOT / "harness/practice_leakmap.json").read_text(encoding="utf-8"))
    for c in leak["canaries"]:
        assert c not in strip_canaries(f"please use {c} in output")
