"""LLM gateway client with 429 retry and blackout detection."""
from __future__ import annotations

import time
from typing import Any

import httpx


class GatewayClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 45.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.blackout = False
        self.deep_calls = 0
        self.fast_calls = 0

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "valura-fast",
        retries: int = 4,
    ) -> str:
        delay = 0.5
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=2.0)) as client:
                    r = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"model": model, "messages": messages, "temperature": 0},
                    )
                if r.status_code == 429:
                    detail = r.text.lower()
                    if "insufficient_quota" in detail or "quota" in detail:
                        self.blackout = True
                        raise RuntimeError("quota blackout")
                    ra = float(r.headers.get("Retry-After") or delay)
                    time.sleep(min(8.0, ra))
                    delay = min(delay * 2, 8.0)
                    last_err = RuntimeError("429")
                    continue
                r.raise_for_status()
                data = r.json()
                if model == "valura-deep":
                    self.deep_calls += 1
                else:
                    self.fast_calls += 1
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
                if "blackout" in str(e).lower() or "quota" in str(e).lower():
                    self.blackout = True
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 8.0)
        raise RuntimeError(f"LLM failed: {last_err}")

    def polish_answer(self, prompt: str, answer: str, value: Any) -> str:
        if self.blackout:
            return answer
        msg = [
            {
                "role": "system",
                "content": (
                    "Rewrite the answer prose for clarity. Do NOT change any numbers, "
                    "dates, or masked identifiers. Do not add recommendations. "
                    "Return only the rewritten answer sentence(s)."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {prompt}\nValue: {value}\nDraft: {answer}",
            },
        ]
        try:
            return self.chat(msg, model="valura-fast", retries=1)
        except Exception:
            return answer
