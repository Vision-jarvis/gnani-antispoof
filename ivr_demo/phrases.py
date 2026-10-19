"""Randomised challenge phrases and the phrase-match check (Part C, steps 1 and 2).

A challenge is four random digits (spoken as words, because the Timbre docs warn that raw digit
strings are mispronounced) followed by a short sentence. A replayed old recording cannot contain a
fresh random digit string, which is what makes the phrase check a liveness signal.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import numpy as np

DIGIT_WORDS = {
    "hi-IN": ("शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ"),
    "kn-IN": ("ಸೊನ್ನೆ", "ಒಂದು", "ಎರಡು", "ಮೂರು", "ನಾಲ್ಕು", "ಐದು", "ಆರು", "ಏಳು", "ಎಂಟು", "ಒಂಬತ್ತು"),
    "en-IN": ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
}
SENTENCES = {
    "hi-IN": ("मेरी आवाज़ ही मेरी पहचान है",),
    "kn-IN": ("ನನ್ನ ಧ್ವನಿ ನನ್ನ ಗುರುತು",),  # "nanna dhwani nanna guruthu", the statement's example
    "en-IN": ("my voice is my identity",),
}
MATCH_THRESHOLD = 0.25  # normalised edit distance at or below this counts as a match


@dataclass(frozen=True)
class Challenge:
    language: str
    digits: tuple[int, ...]
    text: str


def make_challenge(language: str, rng: np.random.Generator, n_digits: int = 4) -> Challenge:
    digits = tuple(int(d) for d in rng.integers(0, 10, n_digits))
    words = " ".join(DIGIT_WORDS[language][d] for d in digits)
    sentence = SENTENCES[language][int(rng.integers(len(SENTENCES[language])))]
    return Challenge(language, digits, f"{words} {sentence}")


def normalise_text(s: str, language: str = "en-IN") -> str:
    """NFC, lower case, punctuation removed, ASCII and native digits mapped to digit words."""
    s = unicodedata.normalize("NFC", s).lower()
    words = DIGIT_WORDS.get(language, DIGIT_WORDS["en-IN"])
    s = re.sub(r"\d", lambda m: f" {words[unicodedata.digit(m.group())]} ", s)
    s = "".join(ch if (unicodedata.category(ch)[0] in "LMN" or ch.isspace()) else " " for ch in s)
    return " ".join(s.split())


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def phrase_distance(expected: str, heard: str, language: str) -> float:
    """Character-level edit distance between normalised strings, divided by the expected length."""
    e, h = normalise_text(expected, language), normalise_text(heard, language)
    return edit_distance(e, h) / max(1, len(e))


def phrase_matches(expected: str, heard: str, language: str, threshold: float = MATCH_THRESHOLD) -> bool:
    return phrase_distance(expected, heard, language) <= threshold
