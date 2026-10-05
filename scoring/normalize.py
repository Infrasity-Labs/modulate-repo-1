"""Shared text normalisation. Every engine goes through normalize() before WER."""
import re
import unicodedata

from num2words import num2words

_NUM = re.compile(r"\d+(?:[.,]\d+)*(?:st|nd|rd|th)?")


def _number_to_words(match: "re.Match[str]") -> str:
    tok = match.group(0)
    ordinal = tok[-2:] in ("st", "nd", "rd", "th")
    digits = tok[:-2] if ordinal else tok
    digits = digits.replace(",", "")
    try:
        if "." in digits:
            return num2words(float(digits))
        return num2words(int(digits), to="ordinal" if ordinal else "cardinal")
    except (ValueError, OverflowError):
        return tok


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\[[^\]]*\]|<[^>]*>", " ", text)  # drop [noise] / <tag> markers
    text = text.replace("%", " percent").replace("&", " and ")
    text = _NUM.sub(lambda m: " " + _number_to_words(m) + " ", text)
    text = re.sub(r"[-‐-―]", " ", text)  # hyphens split words
    text = re.sub(r"[^\w\s']", " ", text)  # punctuation removed, apostrophes kept
    text = re.sub(r"(?<!\w)'|'(?!\w)", " ", text)  # stray quote marks
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()
