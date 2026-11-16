"""Typing by voice into whatever box has keyboard focus. Reusable: nothing here belongs to one GSPro screen. The
caller puts focus in the box (a click) and then turns this on.

Spoken: the NATO words for letters, and extended characters (space, underscore, dash, comma, period,
parenthesis, number sign, plus sign). Each is sent as a keystroke, so the box must have focus. Backspace
deletes the last character typed here, so a misheard one can be taken back.

Parenthesis alternates: the first one typed is "(" and the next is ")". It works from what is already typed, so
backspacing a "(" also brings back the "(" rule. Nesting and mismatched brackets are not handled.
"""

import logging

from app.gspro_screens import GRID_WORDS

log = logging.getLogger(__name__)

PARENTHESIS = "parenthesis"  # the spoken phrase for both brackets: first "(", then ")"

# Spoken phrase -> (character typed, key sent, whether shift is held). Letters are the NATO words in order.
CHARACTERS: dict[str, tuple[str, str, bool]] = {
    word: (chr(ord("a") + index), chr(ord("a") + index), False) for index, word in enumerate(GRID_WORDS)
}
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

_active = False
_typed = ""
_punctuation = False  # the legend shows the punctuation words instead of the NATO letters
PUNCTUATION_WORDS: tuple[str, ...] = ("space", "underscore", "dash", "comma", "period", "parenthesis", "number sign", "plus sign")


def accepts(phrase: str) -> bool:
    """True for a phrase this entry types: a NATO word, an extended character, or parenthesis."""
    return phrase in CHARACTERS or phrase == PARENTHESIS


def active() -> bool:
    return _active


def punctuation() -> bool:
    return _punctuation


def set_punctuation(on: bool) -> None:
    global _punctuation
    _punctuation = on


def typed() -> str:
    return _typed


def start() -> None:
    """Turn typing on with nothing typed yet."""
    global _active, _typed, _punctuation
    _active = True
    _typed = ""
    _punctuation = False


def stop() -> None:
    global _active
    _active = False


def type_phrase(phrase: str) -> str:
    """Type what a phrase means. Returns the character typed."""
    global _typed
    if phrase == PARENTHESIS:
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
