from .assemblyai import AssemblyAI
from .deepgram import Deepgram
from .slot_a import SlotA
from .slot_b import SlotB
from .velma import Velma

ENGINES = {
    "velma": Velma,
    "deepgram": Deepgram,
    "assemblyai": AssemblyAI,
    "slot_a": SlotA,
    "slot_b": SlotB,
}
