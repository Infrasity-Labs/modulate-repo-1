from .assemblyai import AssemblyAI
from .deepgram import Deepgram
from .slot_a import SlotA
from .slot_b import SlotB
from .moonshine_local import MoonshineBase, MoonshineTiny
from .velma import Velma
from .whisper_cpp_local import WhisperCppBase, WhisperCppTiny
from .whisper_hf import WhisperHF

ENGINES = {
    "velma": Velma,
    "deepgram": Deepgram,
    "assemblyai": AssemblyAI,
    "whisper_hf": WhisperHF,
    "moonshine_tiny": MoonshineTiny,
    "moonshine_base": MoonshineBase,
    "whisper_cpp_tiny": WhisperCppTiny,
    "whisper_cpp_base": WhisperCppBase,
    "slot_a": SlotA,
    "slot_b": SlotB,
}
