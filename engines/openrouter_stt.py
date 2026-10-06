"""Speech-to-text models served through OpenRouter (hosted).

Docs: https://openrouter.ai/google/chirp-3 and https://openrouter.ai/microsoft/mai-transcribe-2
POST https://openrouter.ai/api/v1/audio/transcriptions, header `Authorization: Bearer <key>`,
JSON body {"model": ..., "input_audio": {"data": <base64 WAV>, "format": "wav"}, "language": "en"}.
The optional `language` (ISO-639-1) is pinned to "en"; it is auto-detected when omitted, and in testing
Chirp 3 returned French for an unintelligible English clip. Deepgram and AssemblyAI are pinned too.
Response: {"text": ..., "usage": {"seconds", "total_tokens", "cost"}}; errors 400 and 502.
The API accepts WAV, so each file is converted once to 16 kHz mono WAV (untimed) and base64
encoded before the timer starts. Latency covers the HTTP request only: upload of the base64
body, server-side transcription and the response. Both models are routed upstream by OpenRouter,
so latency depends on OpenRouter and the upstream provider as well as the model.

Spend guard: the response reports the real charge in usage.cost. Every successful call (tests
and warm-ups included) is added to a ledger, results/.spend_<engine>.json (git-ignored). Before
each call the engine stops with FatalEngineError if the ledger plus a safety margin would pass
the engine's budget cap, so a run can never cross the agreed estimate.
"""
import base64
import json
import os
import random
import time
from pathlib import Path

import requests

from .audio_utils import to_wav16k
from .base import Engine, FatalEngineError, Transcription

URL = "https://openrouter.ai/api/v1/audio/transcriptions"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}
FATAL_STATUS = {401, 402, 403}  # bad key, no credits, or key limit reached
LEDGER_DIR = Path(__file__).resolve().parent.parent / "results"


class OpenRouterSTT(Engine):
    model_id = ""
    budget_usd = 0.0  # hard cap for everything spent through this engine

    def __init__(self, model: str = None, max_retries: int = 8, timeout: float = 300):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (put it in .env)")
        self._key = key
        self.model = model or self.model_id
        self.max_retries = max_retries
        self.timeout = timeout
        self._ledger = LEDGER_DIR / f".spend_{self.name}.json"
        self.spent = json.loads(self._ledger.read_text())["usd"] if self._ledger.exists() else 0.0
        self._max_call = 0.0  # largest single charge seen, used as the safety margin

    def _record(self, cost: float):
        self.spent += cost
        self._max_call = max(self._max_call, cost)
        self._ledger.write_text(json.dumps({"engine": self.name, "usd": round(self.spent, 6)}))

    def _prepare(self, audio_path: str) -> str:
        with open(to_wav16k(audio_path), "rb") as f:
            return base64.b64encode(f.read()).decode()

    def _post(self, b64: str):
        if self.spent + 1.5 * self._max_call >= self.budget_usd:
            raise FatalEngineError(
                f"budget cap reached for {self.name}: spent ${self.spent:.4f} of ${self.budget_usd:.4f}")
        last = None
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            r, wait = None, None
            try:
                r = requests.post(URL, headers={"Authorization": f"Bearer {self._key}"},
                                  json={"model": self.model, "input_audio": {"data": b64, "format": "wav"}, "language": "en"},
                                  timeout=self.timeout)
            except requests.RequestException as e:
                last = f"network error: {type(e).__name__}"
            else:
                latency = time.perf_counter() - start
                if r.status_code == 200:
                    data = r.json()
                    cost = float((data.get("usage") or {}).get("cost") or 0.0)
                    self._record(cost)
                    return data, latency, cost
                if r.status_code in FATAL_STATUS:
                    raise FatalEngineError(f"OpenRouter returned HTTP {r.status_code}: {r.text[:200]}")
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code not in RETRY_STATUS:
                    break
                wait = self._retry_after(r)
            if attempt < self.max_retries:
                time.sleep((wait if r is not None and wait else min(30, 2 ** attempt)) + random.random())
        raise RuntimeError(last)

    @staticmethod
    def _retry_after(r):
        """Seconds the provider asks us to wait (Retry-After header or error metadata), if any."""
        try:
            return float(r.headers.get("Retry-After") or r.json()["error"]["metadata"]["retry_after_seconds"])
        except (KeyError, TypeError, ValueError):
            return None

    def warmup(self, audio_path: str) -> None:
        self._post(self._prepare(audio_path))

    def transcribe(self, audio_path: str) -> Transcription:
        b64 = self._prepare(audio_path)  # conversion and encoding happen before the timer
        try:
            data, latency, cost = self._post(b64)
        except RuntimeError as e:
            raise RuntimeError(f"OpenRouter ({self.model}) request failed for {audio_path}: {e}")
        return Transcription(text=(data.get("text") or "").strip(), latency_s=latency,
                             duration_s=(data.get("usage") or {}).get("seconds"), raw=data, cost_usd=cost)


class Chirp3(OpenRouterSTT):
    name = "chirp_3"
    model_id = "google/chirp-3"
    price_per_hour = 0.961  # $0.000267 per second x 3600
    budget_usd = 0.36  # estimate for 60 files x 3 repeats is about $0.37


class MaiTranscribe2(OpenRouterSTT):
    name = "mai_transcribe_2"
    model_id = "microsoft/mai-transcribe-2"
    price_per_hour = 0.10
    budget_usd = 0.038  # estimate for 60 files x 3 repeats is about $0.038
