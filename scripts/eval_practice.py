#!/usr/bin/env python
"""Score all practice questions through the orchestrator (no HTTP)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.config import Settings
from valura_arena.service import Service


def main() -> int:
    import os

    os.environ.setdefault("BOOK_PATH", str(ROOT / "data/client_book.json"))
    os.environ.setdefault("MARKET_PATH", str(ROOT / "data/market_data.json"))
    os.environ.setdefault("DATA_DIR", str(ROOT / ".var"))
    os.environ.setdefault("USE_FINAL_FILTER", "true")
    # avoid needing live LLM for local eval
    os.environ["USE_AGNO_TEAM"] = "false"

    qs = [
        json.loads(line)
        for line in (ROOT / "questions/practice_questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    key = json.loads((ROOT / "harness/practice_key.json").read_text(encoding="utf-8"))
    svc = Service(Settings.from_env())
    svc.startup()

    # import scorer helpers
    sys.path.insert(0, str(ROOT / "harness"))
    import score as S

    transcript = []
    for q in qs:
        ans = svc.answer(q["question_id"], q["client_id"], q["prompt"])
        transcript.append(
            {
                "question_id": q["question_id"],
                "client_id": q["client_id"],
                "prompt": q["prompt"],
                "response": ans,
                "in_deadline": True,
                "latency_s": 0.01,
            }
        )

    leak = json.loads((ROOT / "harness/practice_leakmap.json").read_text(encoding="utf-8"))
    card = S.score_run(key, leak, transcript, usage={}, roster=svc.roster())
    out = ROOT / "runs/latest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.jsonl").write_text(
        "\n".join(json.dumps(t) for t in transcript), encoding="utf-8"
    )
    (out / "scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    (out / "roster.json").write_text(json.dumps(svc.roster(), indent=2), encoding="utf-8")
    print(S.render(card) if hasattr(S, "render") else json.dumps(card, indent=2)[:3000])
    # per-miss summary
    scorer = S.Scorer(key, leak)
    misses = []
    for rec in transcript:
        r = scorer.score_question(rec["question_id"], rec, None)
        if r["marks"] < r["marks_available"]:
            misses.append(r)
            print(
                f"MISS {r['question_id']} {r['kind']} {r['marks']}/{r['marks_available']} {r['notes'][:2]}"
            )
    print(f"misses={len(misses)} / {len(transcript)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
