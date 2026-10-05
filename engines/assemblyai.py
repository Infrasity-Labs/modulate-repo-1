from .base import Engine, EngineNotConfigured, Transcription


class AssemblyAI(Engine):
    name = "assemblyai"

    def __init__(self, *args, **kwargs):
        raise EngineNotConfigured(
            "AssemblyAI is not configured yet. Implement transcribe() in engines/assemblyai.py "
            "and set its API key in .env."
        )

    def transcribe(self, audio_path: str) -> Transcription:
        raise EngineNotConfigured("AssemblyAI is not configured yet.")
