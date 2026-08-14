"""Service bootstrap: ingest DBs and build orchestrator."""
from __future__ import annotations

from pathlib import Path

from valura_arena.agents.roster import ROSTER, build_agno_team
from valura_arena.config import Settings
from valura_arena.db.sqlite_repo import BookRepo
from valura_arena.db.vector_repo import VectorRepo, build_chroma_from_sqlite
from valura_arena.ingest.build_sqlite import build_sqlite
from valura_arena.llm.gateway_client import GatewayClient
from valura_arena.observability.trace import TraceLog
from valura_arena.pipeline.orchestrator import Orchestrator


class Service:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.trace = TraceLog(Path(self.settings.sqlite_path).parent / "trace.jsonl")
        self.ready = False
        self.agno_team = None
        self.orchestrator: Orchestrator | None = None
        self.llm: GatewayClient | None = None

    def startup(self) -> None:
        s = self.settings
        conn = build_sqlite(s.book_path, s.market_path, s.sqlite_path)
        repo = BookRepo(conn)
        vector = None
        if s.features.USE_CHROMA:
            vector = VectorRepo(
                s.chroma_path,
                use_chroma=True,
                use_embeddings=s.features.USE_LOCAL_EMBEDDINGS,
            )
            build_chroma_from_sqlite(repo, vector)
        self.llm = GatewayClient(s.llm_base_url, s.llm_api_key)
        if s.features.USE_AGNO_TEAM:
            self.agno_team = build_agno_team(s.llm_base_url, s.llm_api_key)
            self.trace.emit("agno_team", loaded=self.agno_team is not None)
        self.orchestrator = Orchestrator(repo, vector, s, llm=self.llm)
        self.ready = True
        self.trace.emit("startup_ok", sqlite=str(s.sqlite_path))

    def roster(self) -> dict:
        return ROSTER

    def answer(self, question_id: str, client_id: str, prompt: str) -> dict:
        assert self.orchestrator is not None
        t0 = __import__("time").time()
        try:
            out = self.orchestrator.answer(question_id, client_id, prompt)
        except Exception as e:
            self.trace.emit("ALERT_answer_error", error=str(e), qid=question_id)
            out = {
                "question_id": question_id,
                "answer": "",
                "answer_value": None,
                "abstained": True,
                "refused": False,
                "reason": f"internal error: {type(e).__name__}",
                "citations": [],
                "confidence": 0.0,
                "flags": ["upstream_issue"],
                "agents": ["router"],
            }
        latency = __import__("time").time() - t0
        if latency > 15:
            self.trace.emit("ALERT_slow", qid=question_id, latency=latency)
        return out


_SERVICE: Service | None = None


def get_service() -> Service:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = Service()
        _SERVICE.startup()
    return _SERVICE
