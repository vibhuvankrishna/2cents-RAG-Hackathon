#!/usr/bin/env python
"""Alert on scorecard regressions vs baseline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DIMS = [
    "grounded", "research", "abstention", "orchestration", "safety",
    "robustness", "contract_stability", "cost_latency", "judged_quality",
]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: watch_score_regression.py scorecard.json")
        return 2
    path = Path(sys.argv[1])
    card = json.loads(path.read_text(encoding="utf-8"))
    baseline_path = path.parent / "baseline_scorecard.json"
    print(
        f"availability={card.get('availability')} quality={card.get('quality')} "
        f"gates={card.get('gates_passed')}"
    )
    dims = card.get("dimensions") or {}
    for d in DIMS:
        print(f"  {d}: {dims.get(d)}")
    if baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))
        bd = base.get("dimensions") or {}
        for d in DIMS:
            cur = float(dims.get(d) or 0)
            old = float(bd.get(d) or 0)
            if cur + 0.01 < old:
                print(f"ALERT: {d} dropped {old} -> {cur}")
        aq = float(card.get("quality") or 0)
        bq = float(base.get("quality") or 0)
        if aq + 0.5 < bq:
            print(f"ALERT: quality dropped {bq} -> {aq}")
    else:
        baseline_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
        print("wrote initial baseline_scorecard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
