from .base import Engine, EngineNotConfigured, Transcription


class SlotB(Engine):
    name = "slot_b"

    def __init__(self, *args, **kwargs):
        raise EngineNotConfigured(
            "Slot B is not configured yet. Implement transcribe() in engines/slot_b.py "
            "and set its API key in .env."
        )

    def transcribe(self, audio_path: str) -> Transcription:
        raise EngineNotConfigured("Slot B is not configured yet.")
