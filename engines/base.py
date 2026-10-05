from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class EngineNotConfigured(RuntimeError):
    pass


@dataclass
class Transcription:
    text: str
    latency_s: float
    duration_s: Optional[float] = None  # audio duration reported by the engine, if any
    raw: Optional[dict] = None


class Engine(ABC):
    name: str = ""
    # Published price in USD per hour of audio. None means unknown (left blank in results).
    price_per_hour: Optional[float] = None

    @abstractmethod
    def transcribe(self, audio_path: str) -> Transcription:
        """Transcribe one audio file and return text plus wall-clock latency."""
