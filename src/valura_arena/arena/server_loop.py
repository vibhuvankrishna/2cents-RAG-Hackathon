"""Online arena pull-loop (practice / qualifying / final)."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# src on path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from valura_arena.service import Service
from valura_arena.config import Settings


class ArenaClient:
    def __init__(self, url: str, key: str, mode: str):
        self.url = url.rstrip("/")
        self.key = key
        self.mode = mode

    def _call(self, method: str, path: str, body=None, retries: int = 8):
        sep = "&" if "?" in path else "?"
        full = f"{self.url}{path}{sep}mode={self.mode}"
        delay = 0.5
        for attempt in range(retries):
            req = urllib.request.Request(
                full,
                data=json.dumps(body).encode() if body is not None else None,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.key}",
                },
                method=method,
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                if e.code == 429 and attempt < retries - 1:
                    time.sleep(min(8.0, float(e.headers.get("Retry-After") or delay)))
                    delay = min(delay * 2, 8.0)
                    continue
                raise RuntimeError(f"HTTP {e.code} {path}: {raw[:400]}")
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 8.0)
                    continue
                raise RuntimeError(f"{type(e).__name__}: {e}")

    def book(self):
        return self._call("GET", "/v1/book")

    def market(self):
        return self._call("GET", "/v1/market")

    def roster(self, roster):
        return self._call("POST", "/v1/roster", roster)

    def next(self):
        return self._call("GET", "/v1/next")

    def submit(self, answer):
        return self._call("POST", "/v1/answer", answer)

    def me(self):
        return self._call("GET", "/v1/me")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://ai-arena.twocc.in")
    ap.add_argument("--key", required=True)
    ap.add_argument("--mode", default="practice", choices=["practice", "qualifying", "final"])
    ap.add_argument("--book-out", default=".var/remote_book.json")
    ap.add_argument("--market-out", default=".var/remote_market.json")
    args = ap.parse_args()

    client = ArenaClient(args.url, args.key, args.mode)
    print("fetching book/market…", flush=True)
    book = client.book()
    market = client.market()
    Path(args.book_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.book_out).write_text(json.dumps(book), encoding="utf-8")
    Path(args.market_out).write_text(json.dumps(market), encoding="utf-8")

    import os

    os.environ["BOOK_PATH"] = str(Path(args.book_out).resolve())
    os.environ["MARKET_PATH"] = str(Path(args.market_out).resolve())
    os.environ["LLM_BASE_URL"] = f"{args.url.rstrip('/')}/llm/v1"
    os.environ["LLM_API_KEY"] = args.key

    settings = Settings.from_env()
    svc = Service(settings)
    svc.startup()
    try:
        client.roster(svc.roster())
    except Exception as e:
        print(f"roster: {e}", flush=True)

    n = 0
    while True:
        q = client.next()
        if q.get("done"):
            break
        ans = svc.answer(q["question_id"], q["client_id"], q["prompt"])
        res = client.submit(ans)
        n += 1
        tag = "ok" if res.get("in_deadline") else "LATE"
        fb = res.get("feedback")
        extra = ""
        if fb:
            extra = f" marks={fb.get('marks')}/{fb.get('marks_available')}"
            Path(".var/practice_misses.jsonl").parent.mkdir(parents=True, exist_ok=True)
            if fb.get("marks", 0) < fb.get("marks_available", 0):
                with open(".var/practice_misses.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"q": q, "ans": ans, "fb": fb}) + "\n")
        print(f"  {tag} [{n}] {q['question_id']}{extra} {q['prompt'][:50]}", flush=True)

    me = client.me()
    Path(".var/last_me.json").write_text(json.dumps(me, indent=2), encoding="utf-8")
    print(json.dumps({k: me[k] for k in me if k != "scorecard"}, indent=2))
    if me.get("scorecard"):
        print(json.dumps(me["scorecard"], indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
