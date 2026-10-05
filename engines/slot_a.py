from .base import Engine, EngineNotConfigured, Transcription


class SlotA(Engine):
    name = "slot_a"

    def __init__(self, *args, **kwargs):
        raise EngineNotConfigured(
            "Slot A is not configured yet. Implement transcribe() in engines/slot_a.py "
            "and set its API key in .env."
        )

    def transcribe(self, audio_path: str) -> Transcription:
        raise EngineNotConfigured("Slot A is not configured yet.")
