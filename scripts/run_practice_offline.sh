#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
export BOOK_PATH="${BOOK_PATH:-$ROOT/data/client_book.json}"
export MARKET_PATH="${MARKET_PATH:-$ROOT/data/market_data.json}"
export LLM_BASE_URL="${LLM_BASE_URL:-http://127.0.0.1:8600/v1}"
export LLM_API_KEY="${LLM_API_KEY:-assessment}"
export DATA_DIR="${DATA_DIR:-$ROOT/.var}"

mkdir -p "$ROOT/runs/latest"
# start gateway stub if not up
if ! curl -sf http://127.0.0.1:8600/health >/dev/null 2>&1; then
  echo "starting gateway stub…"
  (cd "$ROOT" && python gateway/llm_gateway.py) &
  sleep 2
fi

echo "starting answer service…"
python -m uvicorn valura_arena.app:app --host 127.0.0.1 --port 8080 &
SVC_PID=$!
trap 'kill $SVC_PID 2>/dev/null || true' EXIT
sleep 3

python "$ROOT/harness/run_assessment.py" \
  --service http://127.0.0.1:8080 \
  --gateway http://127.0.0.1:8600 \
  --questions "$ROOT/questions/practice_questions.jsonl" \
  --out "$ROOT/runs/latest"

python "$ROOT/scripts/score_latest.sh"
