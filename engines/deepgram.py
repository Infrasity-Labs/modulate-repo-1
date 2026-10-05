from .base import Engine, EngineNotConfigured, Transcription


class Deepgram(Engine):
    name = "deepgram"

    def __init__(self, *args, **kwargs):
        raise EngineNotConfigured(
            "Deepgram is not configured yet. Implement transcribe() in engines/deepgram.py "
            "and set its API key in .env."
        )

    def transcribe(self, audio_path: str) -> Transcription:
        raise EngineNotConfigured("Deepgram is not configured yet.")
