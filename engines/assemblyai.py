"""AssemblyAI pre-recorded transcription API (upload, submit, poll).

Docs: https://www.assemblyai.com/docs/getting-started/transcribe-an-audio-file
      https://www.assemblyai.com/docs/pre-recorded-audio/select-the-speech-model
POST /v2/upload (raw bytes) -> upload_url; POST /v2/transcript {audio_url, speech_models};
GET /v2/transcript/{id} until status is completed or error. Header `authorization: <key>`.
Model universal-3-5-pro is marked Recommended in the docs. language_code is pinned to "en"
(auto detection returned Slovenian for English VoxPopuli audio in testing), matching
Deepgram language=en and the English-only Velma model.
Price: $0.21/hour for universal-3-5-pro (https://www.assemblyai.com/pricing).

Latency: `latency_s` is the total wall-clock time from the start of the upload to the
completed transcript (upload + submit + polling), so it is comparable with engines that
upload and transcribe in a single call. The submit-to-final time is kept in
`raw["_timing"]["submit_to_final_s"]`. Polling interval is 0.25 s, so latency has up to
0.25 s of polling granularity.
"""
import os
import random
import time

import requests

from .base import Engine, Transcription

BASE = "https://api.assemblyai.com/v2"
RETRY_STATUS = {429, 500, 502, 503, 504}
PRICES = {"universal-3-5-pro": 0.21, "universal-2": 0.15}


class AssemblyAI(Engine):
    name = "assemblyai"

    def __init__(self, model: str = "universal-3-5-pro", max_retries: int = 5,
                 timeout: float = 300, poll_interval: float = 0.25, max_wait: float = 900):
        key = os.environ.get("ASSEMBLYAI_API_KEY")
        if not key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is not set (put it in .env)")
        self._h = {"authorization": key}
        self.model = model
        self.price_per_hour = PRICES.get(model)
        self.max_retries = max_retries
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    def _request(self, method, url, **kw):
        last = None
        for attempt in range(self.max_retries + 1):
            try:
                r = requests.request(method, url, headers=self._h, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                last = f"network error: {type(e).__name__}"
            else:
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                if r.status_code not in RETRY_STATUS:
                    break
            if attempt < self.max_retries:
                time.sleep(min(30, 2 ** attempt) + random.random())
        raise RuntimeError(last)

    def transcribe(self, audio_path: str) -> Transcription:
        try:
            with open(audio_path, "rb") as f:
                body = f.read()
            t0 = time.perf_counter()
            up = self._request("POST", f"{BASE}/upload", data=body)
            t_submit = time.perf_counter()
            job = self._request("POST", f"{BASE}/transcript",
                                json={"audio_url": up["upload_url"],
                                      "speech_models": [self.model],
                                      "language_code": "en"})
            while True:
                if time.perf_counter() - t_submit > self.max_wait:
                    raise RuntimeError("timed out waiting for transcript")
                time.sleep(self.poll_interval)
                data = self._request("GET", f"{BASE}/transcript/{job['id']}")
                if data["status"] == "completed":
                    break
                if data["status"] == "error":
                    raise RuntimeError(f"transcription error: {data.get('error')}")
            t_end = time.perf_counter()
        except RuntimeError as e:
            raise RuntimeError(f"AssemblyAI request failed for {audio_path}: {e}")
        data["_timing"] = {"upload_s": round(t_submit - t0, 3),
                           "submit_to_final_s": round(t_end - t_submit, 3)}
        return Transcription(text=data.get("text") or "", latency_s=t_end - t0,
                             duration_s=data.get("audio_duration"), raw=data)
