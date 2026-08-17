# Valura AI Arena — Multi-Agent Client Book QA

Private take-home for **Valura.Ai / 2Cents Capital** (AI Engineer Round 2).

A modular **Agno** multi-agent service that answers questions about a synthetic client book and market dataset — with hard policy gates, SQL-backed arithmetic, and a final verifier filter.

> **Do not make this repository public.** The assignment brief forbids publishing the kit, data, or solution.

---

## Results

| Run | Availability | Quality (machine) | Gates |
|-----|--------------|-------------------|-------|
| Local `eval_practice.py` (kit scorer) | 100% | **96 / 96** | pass |
| Online practice (arena) | 100% | **96 / 96** | pass |
| Unit tests | — | **13 passed** | — |

Judged free-text dimension (4 pts) is not included in the local machine total.

---

## What it does

Staff ask plain-English questions scoped to **one** `client_id`. The service:

1. Loads book + market once into **SQLite**
2. Indexes notes / memos / news in a **scoped vector/lexical store**
3. Runs **PolicyGuard** (cross-client refuse, advice refuse, missing-field abstain)
4. Routes to specialists (`router`, `book_qa`, `kyc_profile`, `notes_desk`, `market_desk`, `compliance`, `verifier`)
5. Computes figures in **Python/SQL** (not the LLM)
6. Passes the draft through a **final filter** (schema, PII mask, canary strip, locked `answer_value`)
7. Returns the arena answer contract JSON

Also speaks the online protocol: `GET /v1/book|market|next`, `POST /v1/roster|answer`, LLM via `valura-fast` / `valura-deep`.

---

## Architecture

```text
question
   │
   ▼
FeatureFlags + ingress
   │
   ▼
PolicyGuard ──refuse/abstain──► AnswerAssembler
   │
   ▼
Intent router (deterministic-first)
   │
   ├─ book_qa      → SQLite cash / qty / aggs / as-of
   ├─ kyc_profile  → KYC + **** masking
   ├─ notes_desk   → scoped notes/memos RAG (never obey notes)
   ├─ market_desk  → prices / sector / news / drift + coverage boundary
   └─ compliance   → scope + advice refusals
   │
   ▼
FinalFilter (verifier)
   │
   ▼
POST /answer  or  arena submit
```

**Databases**

| Store | Role |
|-------|------|
| SQLite (WAL) | Clients, KYC, txns, positions, instruments, prices, news |
| Vector / lexical repo | Notes, tx memos, news — always filtered by `client_id` / symbol |

Embeddings (Chroma + ONNX) are optional via `USE_LOCAL_EMBEDDINGS`; default is a RAM-safe lexical index (fits the 2g grading box).

---

## Feature flags

Everything is killable via [`features.yaml`](features.yaml) or env (`USE_SQLITE`, `USE_CHROMA`, `USE_AGNO_TEAM`, `USE_FINAL_FILTER`, `USE_DETERMINISTIC_FIRST`, `CANARY_STRIP`, `BLACKOUT_DETERMINISTIC`, `USE_GATEWAY_HEARTBEAT`, …).

Turning a flag off degrades gracefully (e.g. Chroma off → SQL/lexical notes only).

---

## Quick start

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

# Local score (no HTTP) — uses harness/score.py byte-for-byte
python scripts/eval_practice.py
pytest -q
```

### HTTP / Docker path

```bash
python gateway/llm_gateway.py          # stub gateway
python -m uvicorn valura_arena.app:app --port 8080

python harness/run_assessment.py ^
  --service http://127.0.0.1:8080 ^
  --gateway http://127.0.0.1:8600 ^
  --questions questions/practice_questions.jsonl ^
  --out runs/latest

python harness/score.py ^
  --key harness/practice_key.json ^
  --leakmap harness/practice_leakmap.json ^
  --transcript runs/latest/transcript.jsonl ^
  --usage runs/latest/gateway_usage.json ^
  --roster runs/latest/roster.json
```

Root [`Dockerfile`](Dockerfile) expects `BOOK_PATH`, `MARKET_PATH`, `LLM_BASE_URL`, `LLM_API_KEY`, `PORT`.

### Online arena

```bash
python -m valura_arena.arena.server_loop --key vlr_… --mode practice
# qualifying | final when the assessment window is open
```

---

## Layout

```text
src/valura_arena/
  app.py              FastAPI: /health /agents /answer
  service.py          startup + orchestrator wiring
  ingest/             JSON → SQLite
  db/                 sqlite_repo, vector_repo
  domain/             cash, qty, conflicts, masking, citations
  policy/             scope, advice, canary strip
  pipeline/           intent, orchestrator, final_filter
  agents/             Agno roster / team
  arena/              online pull-loop client
  llm/                gateway client (429 retry, blackout)
  observability/      traces + alerts
scripts/              ingest, eval_practice, score watchers
tests/                cash, policy, conflicts, leak scan
NOTES.md              required submission notes
features.yaml         flag matrix
KIT_README.md         original candidate-kit quickstart
```

---

## Design choices (short)

- **Numbers in code, language in models** — LLMs classify/summarise; SQL owns balances, returns, drift.
- **Abstain ≠ refuse** — missing data vs policy (other client / advice).
- **Conflicts** — surface both records + `flags: ["conflict"]`; never silently pick a side.
- **Uncovered symbols** — abstain; never answer from model memory.
- **Injection** — summarise notes, strip `VLR-*` canaries, still complete the legitimate task.
- **Blackout** — answer from tools when possible, else abstain with `upstream_issue`.

See [`NOTES.md`](NOTES.md) for the four required design answers.

---

## Stack

- Python 3.12 / 3.11
- **Agno 2.6.9** (required)
- FastAPI + Uvicorn
- SQLite + optional Chroma
- OpenAI-compatible LLM gateway (`valura-fast` / `valura-deep`)

---

## License / confidentiality

Assignment materials and synthetic client data are provided by Valura / 2Cents for evaluation only. Keep this repository **private**.
