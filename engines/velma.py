"""Modulate Velma Transcribe batch API.

Source: https://docs.modulate.ai/api-reference/stt/batch-english-vfast
POST multipart/form-data, header X-API-Key, file field `upload_file`.
Response JSON has `text` and `duration_ms`. Errors: 429 means credits, concurrency
or monthly limit; 503 means service unavailable.
Prices (USD per hour of audio, batch) from https://www.modulate.ai/api-pricing.
"""
import os
import random
import time

import requests

from .base import Engine, Transcription

BASE_URL = "https://platform.modulate.ai/api"
MODELS = {
    "english-fast": ("velma-2-stt-batch-english-vfast", 0.025),
    "multilingual": ("velma-2-stt-batch", 0.03),
    "multilingual-fast": ("velma-2-stt-batch-multilingual-vfast", 0.03),
}
RETRY_STATUS = {429, 502, 503, 504}


class Velma(Engine):
    name = "velma"

    def __init__(self, model: str = "english-fast", max_retries: int = 5, timeout: float = 300):
        if model not in MODELS:
            raise ValueError(f"unknown Velma model {model!r}, choose from {sorted(MODELS)}")
        key = os.environ.get("VELMA_API_KEY")
        if not key:
            raise RuntimeError("VELMA_API_KEY is not set (put it in .env)")
        self._key = key
        self.model = model
        self.endpoint = f"{BASE_URL}/{MODELS[model][0]}"
        self.price_per_hour = MODELS[model][1]
        self.max_retries = max_retries
        self.timeout = timeout

    def transcribe(self, audio_path: str) -> Transcription:
        last = None
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            try:
                with open(audio_path, "rb") as f:
                    resp = requests.post(
                        self.endpoint,
                        headers={"X-API-Key": self._key},
                        files={"upload_file": f},
                        timeout=self.timeout,
                    )
            except requests.RequestException as e:
                last = f"network error: {type(e).__name__}"
            else:
                latency = time.perf_counter() - start
                if resp.status_code == 200:
                    data = resp.json()
                    ms = data.get("duration_ms")
                    return Transcription(
                        text=data.get("text", ""),
                        latency_s=latency,
                        duration_s=ms / 1000 if ms is not None else None,
                        raw=data,
                    )
                last = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code not in RETRY_STATUS:
                    break  # 400/401/413 etc. will not succeed on retry
            if attempt < self.max_retries:
                time.sleep(min(30, 2 ** attempt) + random.random())
        raise RuntimeError(f"Velma request failed for {audio_path}: {last}")
