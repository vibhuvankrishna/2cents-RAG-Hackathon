#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python "$ROOT/harness/score.py" \
  --key "$ROOT/harness/practice_key.json" \
  --leakmap "$ROOT/harness/practice_leakmap.json" \
  --transcript "$ROOT/runs/latest/transcript.jsonl" \
  --usage "$ROOT/runs/latest/gateway_usage.json" \
  --roster "$ROOT/runs/latest/roster.json" \
  --out "$ROOT/runs/latest/scorecard.json"
python "$ROOT/scripts/watch_score_regression.py" "$ROOT/runs/latest/scorecard.json"
