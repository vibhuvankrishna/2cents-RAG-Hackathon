"""FastAPI HTTP surface for offline grading + Docker."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# allow `python -m valura_arena.app` from src layout
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI
from pydantic import BaseModel, Field

from valura_arena.service import get_service

app = FastAPI(title="Valura Arena Answer Service", version="0.1.0")


class AnswerIn(BaseModel):
    question_id: str
    client_id: str
    prompt: str


@app.on_event("startup")
def _startup() -> None:
    get_service()


@app.get("/health")
def health():
    svc = get_service()
    return {"ok": True, "ready": svc.ready}


@app.get("/agents")
def agents():
    return get_service().roster()


@app.post("/answer")
def answer(body: AnswerIn):
    return get_service().answer(body.question_id, body.client_id, body.prompt)


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("valura_arena.app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
