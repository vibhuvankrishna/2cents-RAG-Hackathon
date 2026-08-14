"""Scoped vector/lexical store for notes, memos, news.

Default path is a lexical inverted index (no model download) so Docker stays
inside 2g RAM. Set USE_LOCAL_EMBEDDINGS=true to enable Chroma+ONNX embeddings.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any


class VectorRepo:
    def __init__(self, path: Path, use_chroma: bool = True, use_embeddings: bool = False):
        self.path = path
        self.use_embeddings = bool(use_chroma and use_embeddings)
        self._docs: dict[str, list[dict[str, Any]]] = {
            "notes": [],
            "tx_memos": [],
            "news": [],
        }
        self._collections = None
        self._client = None
        if self.use_embeddings:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                self.path.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.path),
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collections = {
                    "notes": self._client.get_or_create_collection("notes"),
                    "tx_memos": self._client.get_or_create_collection("tx_memos"),
                    "news": self._client.get_or_create_collection("news"),
                }
            except Exception:
                self.use_embeddings = False
                self._collections = None

    def clear(self) -> None:
        self._docs = {"notes": [], "tx_memos": [], "news": []}
        if self._collections and self._client:
            for name in list(self._collections):
                try:
                    self._client.delete_collection(name)
                except Exception:
                    pass
            self._collections = {
                "notes": self._client.get_or_create_collection("notes"),
                "tx_memos": self._client.get_or_create_collection("tx_memos"),
                "news": self._client.get_or_create_collection("news"),
            }

    def add(self, collection: str, doc_id: str, text: str, metadata: dict) -> None:
        text = text or ""
        self._docs.setdefault(collection, []).append(
            {"id": doc_id, "text": text, "metadata": metadata}
        )
        if self.use_embeddings and self._collections and collection in self._collections:
            meta = {k: ("" if v is None else str(v)) for k, v in metadata.items()}
            self._collections[collection].upsert(
                ids=[doc_id], documents=[text], metadatas=[meta]
            )

    def query(
        self,
        collection: str,
        query: str,
        *,
        client_id: str | None = None,
        symbol: str | None = None,
        n: int = 8,
    ) -> list[dict]:
        if self.use_embeddings and self._collections:
            where: dict | None = None
            if client_id:
                where = {"client_id": client_id}
            elif symbol:
                where = {"symbol": symbol}
            try:
                res = self._collections[collection].query(
                    query_texts=[query or "summary"],
                    n_results=n,
                    where=where,
                )
                out = []
                ids = (res.get("ids") or [[]])[0]
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                for i, d, m in zip(ids, docs, metas):
                    out.append({"id": i, "text": d, "metadata": m or {}})
                if out:
                    return out
            except Exception:
                pass
        tokens = set(re.findall(r"[a-z0-9]+", (query or "").lower()))
        scored = []
        for d in self._docs.get(collection, []):
            md = d["metadata"]
            if client_id and md.get("client_id") != client_id:
                continue
            if symbol and md.get("symbol") != symbol:
                continue
            text = d["text"].lower()
            score = sum(1 for t in tokens if t in text) + min(len(d["text"]), 200) * 0.001
            scored.append((score, d))
        scored.sort(key=lambda x: -x[0])
        return [d for _, d in scored[:n]]


def build_chroma_from_sqlite(repo, vector: VectorRepo) -> None:
    vector.clear()
    for row in repo.conn.execute("SELECT * FROM notes").fetchall():
        vector.add(
            "notes",
            row["id"],
            row["text"] or "",
            {
                "client_id": row["client_id"],
                "date": row["date"] or "",
                "author": row["author"] or "",
            },
        )
    for row in repo.conn.execute(
        "SELECT id, client_id, date, symbol, memo FROM transactions "
        "WHERE memo IS NOT NULL AND memo != ''"
    ).fetchall():
        vector.add(
            "tx_memos",
            row["id"],
            row["memo"] or "",
            {
                "client_id": row["client_id"],
                "date": row["date"] or "",
                "symbol": row["symbol"] or "",
            },
        )
    for row in repo.conn.execute("SELECT * FROM news").fetchall():
        text = f"{row['headline'] or ''}\n{row['body'] or ''}"
        vector.add(
            "news",
            row["id"],
            text,
            {"symbol": row["symbol"] or "", "date": row["date"] or ""},
        )
