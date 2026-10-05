import pytest

from scoring.normalize import normalize
from scoring.wer import compute_wer


def test_case_and_punctuation():
    assert normalize("Hello, World!") == "hello world"


def test_apostrophes_kept():
    assert normalize("Don't stop") == "don't stop"
    assert normalize("it’s") == "it's"


def test_hyphen_splits():
    assert normalize("well-known") == "well known"


def test_numbers():
    assert normalize("I have 3 cats") == "i have three cats"
    assert normalize("the 2nd one") == "the second one"
    assert normalize("1,000 people") == "one thousand people"


def test_percent_and_tags():
    assert normalize("50% [laughter] done") == "fifty percent done"


def test_empty():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_wer_zero_when_only_formatting_differs():
    assert compute_wer(["Hello, world."], ["hello world"]) == 0.0


def test_wer_value():
    assert compute_wer(["a b c d"], ["a b x d"]) == pytest.approx(0.25)


def test_wer_empty_hypothesis_is_one():
    assert compute_wer(["a b"], [""]) == pytest.approx(1.0)


def test_wer_all_empty_refs_raises():
    with pytest.raises(ValueError):
        compute_wer([""], ["x"])
