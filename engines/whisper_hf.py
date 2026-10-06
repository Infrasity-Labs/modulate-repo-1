"""Whisper large-v3 via Hugging Face Inference Providers, provider DeepInfra (hosted).

Docs: https://huggingface.co/docs/inference-providers/tasks/automatic-speech-recognition
Client: huggingface_hub.InferenceClient(provider="deepinfra").automatic_speech_recognition(...)
Model ID: openai/whisper-large-v3 (Hugging Face maps it to the same ID at DeepInfra).

Provider choice: Groq is not a provider for this model on Hugging Face. DeepInfra is, and it
publishes a per-minute price of $0.00045 per audio minute (https://deepinfra.com/openai/whisper-large-v3),
which is $0.027 per audio hour. Hugging Face passes provider rates through with no markup
(https://huggingface.co/docs/inference-providers/pricing). DeepInfra's page mentions a minimum
charge per request without giving the amount, so real spend per call may be a little higher
for very short clips.
Latency covers the whole routed call (Hugging Face router plus DeepInfra queue and compute), so
it depends on the provider as well as the model. The audio file is read before the timer starts.
warmup() makes one untimed call so a cold start is not counted in the measured calls.
"""

import os
import random
import time

from .base import Engine, FatalEngineError, Transcription

MODEL_ID = "openai/whisper-large-v3"
PROVIDER = "deepinfra"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}
FATAL_STATUS = {401, 402, 403}  # bad or under-permissioned token, or credits exhausted


class WhisperHF(Engine):
    name = "whisper_hf"
    price_per_hour = 0.027  # $0.00045 per minute x 60

    def __init__(self, model: str = MODEL_ID, max_retries: int = 4, timeout: float = 300):
        from huggingface_hub import InferenceClient

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is not set (put it in .env)")
        self.model = f"{model} via Hugging Face ({PROVIDER})"
        self._model_id = model
        self._client = InferenceClient(provider=PROVIDER, api_key=token, timeout=timeout)
        self.max_retries = max_retries

    def _call(self, audio: bytes):
        return self._client.automatic_speech_recognition(audio, model=self._model_id)

    def warmup(self, audio_path: str) -> None:
        with open(audio_path, "rb") as f:
            audio = f.read()
        try:
            self._call(audio)
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in FATAL_STATUS:
                raise FatalEngineError(f"Hugging Face returned HTTP {status} on warm-up: {str(e)[:200]}")

    def transcribe(self, audio_path: str) -> Transcription:
        with open(audio_path, "rb") as f:
            audio = f.read()
        last = None
        for attempt in range(self.max_retries + 1):
            start = time.perf_counter()
            try:
                out = self._call(audio)
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in FATAL_STATUS:
                    raise FatalEngineError(f"Hugging Face returned HTTP {status}: {str(e)[:200]}")
                last = f"{type(e).__name__} (HTTP {status}): {str(e)[:200]}"
                if status is not None and status not in RETRY_STATUS:
                    break
            else:
                return Transcription(text=(out.text or "").strip(),
                                     latency_s=time.perf_counter() - start, raw={"text": out.text})
            if attempt < self.max_retries:
                time.sleep(min(30, 2 ** attempt) + random.random())
        raise RuntimeError(f"Whisper (HF/{PROVIDER}) request failed for {audio_path}: {last}")
