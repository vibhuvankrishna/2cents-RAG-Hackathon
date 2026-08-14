konatala.vibhuvan.krishna@gmail.com

# Valura AI Arena — NOTES

> Replace the email on line 1 with the exact address used at `/enrol` if different — it ties the repo to your score.

## Build / run / test

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
set PYTHONPATH=src
set BOOK_PATH=data/client_book.json
set MARKET_PATH=data/market_data.json
set LLM_BASE_URL=http://127.0.0.1:8600/v1
set LLM_API_KEY=assessment
set DATA_DIR=.var

python scripts/ingest_local.py
python gateway/llm_gateway.py          # terminal 1 (stub)
python -m uvicorn valura_arena.app:app --port 8080   # terminal 2
python harness/run_assessment.py --service http://127.0.0.1:8080 --gateway http://127.0.0.1:8600 --questions questions/practice_questions.jsonl --out runs/latest
python harness/score.py --key harness/practice_key.json --leakmap harness/practice_leakmap.json --transcript runs/latest/transcript.jsonl --usage runs/latest/gateway_usage.json --roster runs/latest/roster.json

# Fast local score without HTTP:
python scripts/eval_practice.py

pytest -q
```

Online:

```bash
set PYTHONPATH=src
python -m valura_arena.arena.server_loop --key vlr_… --mode practice
# qualifying/final only while the assessment window is open
```

Docker: root `Dockerfile` reads `BOOK_PATH`, `MARKET_PATH`, `LLM_BASE_URL`, `LLM_API_KEY`, `PORT`.

Feature flags: `features.yaml` / matching env vars. Kill switches for SQLite, Chroma/lexical RAG, Agno team, final filter, LLM polish, gateway heartbeat, etc.

## Architecture

Ingress → PolicyGuard → intent router → specialists on **SQLite** (book/market) + **scoped vector/lexical store** (notes/memos/news) → assembler → **FinalFilter/verifier** (schema, canary/PII, locked tool values). Deterministic-first arithmetic. Agno Team declared in roster (`agno==2.6.9`).

## Results (this build)

- Offline `eval_practice.py`: **96/96** machine, availability 100%, gates pass, 0 misses.
- Online practice (`run_6f6a0d94a205c62c`): **96/96**, availability 1.0, gates pass.
- Qualifying attempt 2 blocked: server returns `assessment window has closed` (closed 2026-08-10T23:59 IST). Attempt 1 (stub abstains) remains on file.

## Decisions

- Embedded SQLite + lexical VectorRepo by default (Chroma/ONNX behind `USE_LOCAL_EMBEDDINGS`) to fit 2g grading.
- Snapshot≠ledger → `conflict` flag, do not pick a side.
- Notes are data; canaries stripped; injection questions still engage.

## Four answers

1. **Cannot answer:** tools/policy return presence/absence (missing KYC fields, uncovered symbols, scope/advice). `answer_value` forced null — not model uncertainty.
2. **Hostile note:** neutralized in notes_desk retrieval + `CANARY_STRIP` + FinalFilter. Would need those flags off and a specialist echoing raw secrets.
3. **Provider down:** book/market SQL answers unchanged (`BLACKOUT_DETERMINISTIC`); notes prose/polish degrade; may abstain with `upstream_issue` when no tool path exists. Retries handle transient 429.
4. **Agno:** easy OpenAI-compatible `base_url` + roster. Hard: scoring wants real role paths while tools short-circuit the LLM (`USE_DETERMINISTIC_FIRST` + `USE_GATEWAY_HEARTBEAT`). Confirmed Team/Agent wiring against installed `agno==2.6.9`.

## Next / weak

If the window reopens: run qualifying #2/#3 with heartbeat on, then final. Intent heuristics may need paraphrase expansion on a fresh graded book.
