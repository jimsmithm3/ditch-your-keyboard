"""How close two words sound, for warning about voice commands that may be heard as each other.

A distance of 0 means the same sound. The distance is the number of sound changes needed to turn one pronunciation
into the other, divided by the longer pronunciation, so it runs from 0 to 1. Pronunciations come from the CMU
Pronouncing Dictionary (the cmudict package). A word it does not know falls back to a spelling-based sound code
(Metaphone, from jellyfish), and that pair is marked as not exact.

Scores are saved in the app database (table word_similarity), so each pair is worked out once. Bump SCORING_VERSION
when the method changes, so the old scores are not reused.

A phrase is compared word by word, by position. The first word counts more, because it is the one the recognizer
has to get right before anything else matters.
"""

import sqlite3

import cmudict
import jellyfish

from app.players import db_path

SCORING_VERSION = 2  # 2: pronunciations added for words the dictionary lacks (xray, juliett)
FIRST_WORD_WEIGHT = 2.0  # the first word of a command matters more than the rest

# Words the CMU dictionary does not have, with their pronunciations (stress marks dropped).
PRONUNCIATIONS: dict[str, tuple[str, ...]] = {
    "xray": ("EH", "K", "S", "R", "EY"),
    "juliett": ("JH", "UW", "L", "IY", "EH", "T"),
}

_cmu: dict | None = None
_memory: dict[tuple[str, str], tuple[float, bool]] = {}  # the scores already read this session


def _dictionary() -> dict:
    global _cmu
    if _cmu is None:
        _cmu = cmudict.dict()
    return _cmu


def _phones(word: str) -> tuple[str, ...] | None:
    """The first pronunciation with its stress marks removed, or None if the word is not in the dictionary."""
    if word.lower() in PRONUNCIATIONS:
        return PRONUNCIATIONS[word.lower()]
    prons = _dictionary().get(word.lower())
    if not prons:
        return None
    return tuple(phone.rstrip("012") for phone in prons[0])


def _edit_distance(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    """Levenshtein distance between two sequences of sounds."""
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        current = [i]
        for j, y in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def word_distance(first: str, second: str) -> tuple[float, bool]:
    """(distance from 0 to 1, exact). Not exact means one word was not in the dictionary and the spelling code was used."""
    first, second = first.lower(), second.lower()
    if first == second:
        return 0.0, True
    a, b = _phones(first), _phones(second)
    if a is not None and b is not None:
        return _edit_distance(a, b) / max(len(a), len(b)), True
    code_a, code_b = jellyfish.metaphone(first), jellyfish.metaphone(second)
    if not code_a or not code_b:
        return 1.0, False  # nothing to compare: treat as different
    return jellyfish.levenshtein_distance(code_a, code_b) / max(len(code_a), len(code_b)), False


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS word_similarity (
            word1 TEXT NOT NULL,
            word2 TEXT NOT NULL,
            version INTEGER NOT NULL,
            distance REAL NOT NULL,
            exact INTEGER NOT NULL,
            PRIMARY KEY (word1, word2, version)
        )
        """
    )
    return con


def cached_word_distance(first: str, second: str, con: sqlite3.Connection | None = None) -> tuple[float, bool]:
    """word_distance, but read from the saved scores first, and saved when it is worked out."""
    key = tuple(sorted((first.lower(), second.lower())))
    if key in _memory:
        return _memory[key]
    own = con is None
    con = con or _connect()
    try:
        row = con.execute(
            "SELECT distance, exact FROM word_similarity WHERE word1 = ? AND word2 = ? AND version = ?",
            (key[0], key[1], SCORING_VERSION),
        ).fetchone()
        if row is None:
            distance, exact = word_distance(*key)
            con.execute(
                "INSERT OR REPLACE INTO word_similarity (word1, word2, version, distance, exact) VALUES (?, ?, ?, ?, ?)",
                (key[0], key[1], SCORING_VERSION, distance, int(exact)),
            )
            con.commit()
            result = (distance, exact)
        else:
            result = (row[0], bool(row[1]))
    finally:
        if own:
            con.close()
    _memory[key] = result
    return result


def phrase_distance(first: str, second: str, con: sqlite3.Connection | None = None) -> tuple[float, bool]:
    """Distance between two commands, word by word by position. A missing word counts as fully different.
    The first word is weighted by FIRST_WORD_WEIGHT. Returns (distance from 0 to 1, all words exact)."""
    a, b = first.split(), second.split()
    total = 0.0
    weight_sum = 0.0
    exact = True
    for position in range(max(len(a), len(b))):
        weight = FIRST_WORD_WEIGHT if position == 0 else 1.0
        if position < len(a) and position < len(b):
            distance, word_exact = cached_word_distance(a[position], b[position], con)
            exact = exact and word_exact
        else:
            distance = 1.0
        total += weight * distance
        weight_sum += weight
    return (total / weight_sum if weight_sum else 1.0), exact


def first_word_distance(first: str, second: str, con: sqlite3.Connection | None = None) -> tuple[float, bool]:
    """Distance between the first words only: the check that matters most."""
    a, b = first.split(), second.split()
    if not a or not b:
        return 1.0, False
    return cached_word_distance(a[0], b[0], con)
