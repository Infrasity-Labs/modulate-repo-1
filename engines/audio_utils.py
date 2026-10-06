"""Shared audio helpers for engines that need 16 kHz mono 16-bit WAV."""
from math import gcd
from pathlib import Path

import soundfile as sf

TARGET_SR = 16000
AUDIO_ROOT = Path(__file__).resolve().parent.parent / "datasets" / "audio"


def to_wav16k(path: str) -> str:
    """Convert any audio file to 16 kHz mono 16-bit WAV once and cache it."""
    src = Path(path).resolve()
    try:
        rel = src.relative_to(AUDIO_ROOT)
    except ValueError:
        rel = Path(src.name)
    dst = AUDIO_ROOT / "_wav16k" / rel.with_suffix(".wav")
    if dst.exists():
        return str(dst)
    audio, sr = sf.read(str(src), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != TARGET_SR:
        from scipy.signal import resample_poly
        g = gcd(int(sr), TARGET_SR)
        audio = resample_poly(audio, TARGET_SR // g, int(sr) // g)
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), audio, TARGET_SR, subtype="PCM_16")
    return str(dst)
