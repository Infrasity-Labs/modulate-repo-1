"""Moonshine, run LOCALLY on this machine with Transformers (no network, no API key).

Model card: https://huggingface.co/moonshine-ai/moonshine-tiny (MIT licence). Usage follows the
card: MoonshineForConditionalGeneration + AutoProcessor, generate with max_length derived from
the input length at 6.5 tokens per second (the card's guard against hallucinated repeats).
Runs on CPU in float32 for reproducibility.

Latency is a LOCAL measurement: wall-clock from decoded audio to decoded text (feature
extraction, generation and token decoding). It excludes model loading, which happens once in
__init__, and excludes the untimed warm-up call. It depends entirely on this machine and on
what else is running, so it must not be compared with hosted API latency, which includes
network and server time. Close other apps during a timed run.
price_per_hour is 0.0: there is no API charge. Local compute and electricity are not counted.
"""
import time

import numpy as np
import soundfile as sf

from .base import Engine, Transcription

TARGET_SR = 16000


class MoonshineLocal(Engine):
    local = True
    price_per_hour = 0.0
    model_id = "moonshine-ai/moonshine-tiny"

    def __init__(self, model: str = None):
        import torch
        from transformers import AutoProcessor, MoonshineForConditionalGeneration

        self._torch = torch
        self._model_id = model or self.model_id
        self.model = self._model_id
        self._proc = AutoProcessor.from_pretrained(self._model_id)
        self._model = MoonshineForConditionalGeneration.from_pretrained(self._model_id).to("cpu").eval()
        self._sr = self._proc.feature_extractor.sampling_rate

    def _load(self, path):
        audio, sr = sf.read(path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != self._sr:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(int(sr), int(self._sr))
            audio = resample_poly(audio, int(self._sr) // g, int(sr) // g).astype(np.float32)
        return audio

    def _run(self, audio):
        torch = self._torch
        inputs = self._proc(audio, return_tensors="pt", sampling_rate=self._sr)
        factor = 6.5 / self._sr
        max_length = int((inputs.attention_mask.sum(dim=-1) * factor).max().item())
        with torch.inference_mode():
            ids = self._model.generate(**inputs, max_length=max(max_length, 8))
        return self._proc.decode(ids[0], skip_special_tokens=True)

    def warmup(self, audio_path: str) -> None:
        self._run(self._load(audio_path))

    def transcribe(self, audio_path: str) -> Transcription:
        start = time.perf_counter()
        text = self._run(self._load(audio_path))
        return Transcription(text=text.strip(), latency_s=time.perf_counter() - start)


class MoonshineTiny(MoonshineLocal):
    name = "moonshine_tiny"
    model_id = "moonshine-ai/moonshine-tiny"


class MoonshineBase(MoonshineLocal):
    name = "moonshine_base"
    model_id = "moonshine-ai/moonshine-base"
