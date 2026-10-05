import jiwer

from .normalize import normalize


def compute_wer(references, hypotheses) -> float:
    """Corpus WER over normalised text. Pairs with an empty reference are dropped."""
    pairs = [(normalize(r), normalize(h)) for r, h in zip(references, hypotheses)]
    pairs = [(r, h) for r, h in pairs if r]
    if not pairs:
        raise ValueError("no non-empty references to score")
    refs, hyps = zip(*pairs)
    return float(jiwer.wer(list(refs), list(hyps)))
