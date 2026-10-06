from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class EngineNotConfigured(RuntimeError):
    pass


class FatalEngineError(Exception):
    """Stops the whole run (for example credits exhausted or a bad token). Not retried."""


@dataclass
class Transcription:
    text: str
    latency_s: float
    duration_s: Optional[float] = None  # audio duration reported by the engine, if any
    raw: Optional[dict] = None
    cost_usd: Optional[float] = None  # actual charge reported by the provider, if any


class Engine(ABC):
    name: str = ""
    # Published price in USD per hour of audio. None means unknown (left blank in results).
    price_per_hour: Optional[float] = None
    local: bool = False  # True when inference runs on this machine instead of a hosted API

    def warmup(self, audio_path: str) -> None:
        """Optional untimed, unscored call before measuring (loads caches, wakes the service)."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> Transcription:
        """Transcribe one audio file and return text plus wall-clock latency."""
