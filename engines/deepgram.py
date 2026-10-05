"""Deepgram pre-recorded transcription API.

Docs: https://developers.deepgram.com/docs/pre-recorded-audio
POST https://api.deepgram.com/v1/listen, header `Authorization: Token <key>`,
raw audio bytes as the body, transcript at results.channels[0].alternatives[0].transcript.
Model nova-3 is the model the docs recommend. smart_format=true is the docs' recommended
formatting setting and is left on; scoring normalisation handles the formatting.
Price: Nova-3 monolingual pay-as-you-go, $0.0043/min = $0.258/hour (https://deepgram.com/pricing).
"""
import os
import random
import time

import requests

from .base import Engine, Transcription

URL = "https://api.deepgram.com/v1/listen"
RETRY_STATUS = {429, 500, 502, 503, 504}


class Deepgram(Engine):
    name = "deepgram"

    def __init__(self, model: str = "nova-3", max_retries: int = 5, timeout: float = 300):
        key = os.environ.get("DEEPGRAM_API_KEY")
        if not key:
            raise RuntimeError("DEEPGRAM_API_KEY is not set (put it in .env)")
        self._key = key
        self.model = model
        self.price_per_hour = 0.258 if model == "nova-3" else None
        self.max_retries = max_retries
        self.timeout = timeout

    def transcribe(self, audio_path: str) -> Transcription:
        with open(audio_path, "rb") as f:
            body = f.read()
        last = None
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            try:
                resp = requests.post(
                    URL,
                    params={"model": self.model, "smart_format": "true", "language": "en"},
                    headers={"Authorization": f"Token {self._key}",
                             "Content-Type": "application/octet-stream"},
                    data=body,
                    timeout=self.timeout,
                )
            except requests.RequestException as e:
                last = f"network error: {type(e).__name__}"
            else:
                latency = time.perf_counter() - start
                if resp.status_code == 200:
                    data = resp.json()
                    alt = data["results"]["channels"][0]["alternatives"][0]
                    dur = (data.get("metadata") or {}).get("duration")
                    return Transcription(text=alt.get("transcript", ""), latency_s=latency,
                                         duration_s=dur, raw=data)
                last = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code not in RETRY_STATUS:
                    break
            if attempt < self.max_retries:
                time.sleep(min(30, 2 ** attempt) + random.random())
        raise RuntimeError(f"Deepgram request failed for {audio_path}: {last}")
