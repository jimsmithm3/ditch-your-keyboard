"""Typing by voice into whatever box has keyboard focus. Reusable: nothing here belongs to one GSPro screen. The
caller puts focus in the box (a click) and then turns this on.

A display is a way of entering text, and it is a screen part of its own kind: it locks out the rest of the screen while
it is on. Its allowed kinds are or'd together, so the course filter allows numbers, letters and punctuation. The words
are spoken and each is sent as a keystroke, so the box must have focus. Backspace deletes the last character typed
here, so a misheard one can be taken back.

Parenthesis alternates: the first one typed is "(" and the next is ")". It works from what is already typed, so
backspacing a "(" also brings back the "(" rule. Nesting and mismatched brackets are not handled.
"""

import logging
from dataclasses import dataclass

from app.commands import DIGIT_KEYS
from app.gspro_screens import GRID_WORDS, PUNCTUATION_WORDS

log = logging.getLogger(__name__)

NUMBER, LETTER, PUNCTUATION, BACKSPACE = "number", "letter", "punctuation", "backspace"  # the kinds a display can allow
GRAMMAR_GROUP: dict[str, str] = {
    NUMBER: "Filter digits", LETTER: "Filter letters", PUNCTUATION: "Filter punctuation", BACKSPACE: "Filter backspace",
}
CONTROL_GROUP = "Filter control"  # end filter: listens whenever the display is on


# Spoken phrase -> (character typed, key sent, whether shift is held). Letters are the NATO words in order.
CHARACTERS: dict[str, tuple[str, str, bool]] = {
    word: (chr(ord("a") + index), chr(ord("a") + index), False) for index, word in enumerate(GRID_WORDS)
}
CHARACTERS.update({word: (digit, digit, False) for word, digit in DIGIT_KEYS.items()})  # "one" types 1
CHARACTERS.update(
    {
        "space": (" ", "space", False),
        "underscore": ("_", "-", True),
        "dash": ("-", "-", False),
        "comma": (",", ",", False),
        "period": (".", ".", False),
        "number sign": ("#", "3", True),
        "plus sign": ("+", "=", True),
    }
)
OPEN_BRACKET = ("(", "9", True)
CLOSE_BRACKET = (")", "0", True)
KIND_OF: dict[str, str] = {
    **{word: NUMBER for word in DIGIT_KEYS},
    **{word: LETTER for word in GRID_WORDS},
    **{word: PUNCTUATION for word in PUNCTUATION_WORDS},
    "backspace": BACKSPACE,  # a property of the display, but it deletes rather than types
}


@dataclass(frozen=True)
class Display:
    """A way of entering text. allowed is the set of kinds it takes; a phrase of another kind is not typed here."""

    name: str
    allowed: frozenset[str]

    def accepts(self, phrase: str) -> bool:
        """True for a phrase this display types. Backspace is allowed but types nothing, so it is not one of these."""
        kind = KIND_OF.get(phrase)
        return (kind in self.allowed and kind != BACKSPACE) or phrase == "parenthesis"

    def grammar_groups(self) -> tuple[str, ...]:
        """The grammar groups that listen while this display is on: its allowed kinds, then the controls."""
        kinds = (kind for kind in (NUMBER, LETTER, PUNCTUATION, BACKSPACE) if kind in self.allowed)
        return (*(GRAMMAR_GROUP[kind] for kind in kinds), CONTROL_GROUP)


# The course filter: numbers, letters and punctuation.
FILTER = Display("filter", frozenset({NUMBER, LETTER, PUNCTUATION, BACKSPACE}))

_active = False
_typed = ""


def accepts(phrase: str) -> bool:
    """True for a phrase the filter types: a number word, a NATO word, an extended character, or parenthesis."""
    return FILTER.accepts(phrase)


def grammar_groups() -> tuple[str, ...]:
    """The grammar groups that listen while typing is on (the filter display's)."""
    return FILTER.grammar_groups()


def active() -> bool:
    return _active


def typed() -> str:
    return _typed


def start() -> None:
    """Turn typing on with nothing typed yet."""
    global _active, _typed
    _active = True
    _typed = ""


def stop() -> None:
    global _active
    _active = False


def type_phrase(phrase: str) -> str:
    """Type what a phrase means. Returns the character typed."""
    global _typed
    if phrase == "parenthesis":
        char, key, shift = CLOSE_BRACKET if _open_bracket() else OPEN_BRACKET
    else:
        char, key, shift = CHARACTERS[phrase]
    _send(key, shift)
    _typed += char
    return char


def backspace() -> bool:
    """Delete the last character typed here. False if nothing has been typed, so nothing is sent."""
    global _typed
    if not _typed:
        return False
    _send("backspace", False)
    _typed = _typed[:-1]
    return True


def _open_bracket() -> bool:
    """True when a "(" is waiting for its ")". Read from what is typed, so backspace keeps it right."""
    return _typed.count("(") > _typed.count(")")


def _send(key: str, shift: bool) -> None:
    import pydirectinput

    if shift:
        pydirectinput.keyDown("shift")
        try:
            pydirectinput.press(key, _pause=False)
        finally:
            pydirectinput.keyUp("shift")
    else:
        pydirectinput.press(key, _pause=False)
