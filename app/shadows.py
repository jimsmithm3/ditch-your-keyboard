"""Shadow levels, "shadow one" to "shadow five". GSPro only has shadow down and shadow up keys, so the app keeps
track of the level the way the club bag does: the first call (or the same level called twice in a row) starts
from the lightest level, so the number of presses is known; after that, moves are relative.
"""

from app.bag import Move

DOWN = "shift+,"  # lighter shadows
UP = "shift+."  # deeper shadows
LOWEST, HIGHEST = 1, 5
STEPS_TO_LOWEST = HIGHEST - LOWEST  # four presses down from the deepest level reach the lightest

WORDS = ("one", "two", "three", "four", "five")
PHRASE_LEVEL: dict[str, int] = {f"shadow {word}": index + 1 for index, word in enumerate(WORDS)}
PHRASES = tuple(PHRASE_LEVEL)

_level: int | None = None  # None until a shadow level has been called, because GSPro may be on any level
_last: int | None = None  # the level called last time, so calling the same one twice resyncs


def spoken_phrases() -> tuple[str, ...]:
    return PHRASES


def apply(phrase: str) -> Move | None:
    """The key presses that take GSPro to the level the phrase names. None if the phrase is not a shadow level."""
    global _level, _last
    if phrase not in PHRASE_LEVEL:
        return None
    target = PHRASE_LEVEL[phrase]
    if _level is None or target == _last:
        downs = [DOWN] * STEPS_TO_LOWEST
        ups = [UP] * (target - LOWEST)
        keys = downs + ups
        detail = f"shadows: start from the lightest, then {target - LOWEST} up"
    else:
        delta = target - _level
        keys = [UP] * delta if delta > 0 else [DOWN] * -delta
        detail = f"shadows {target}"
    _level = target
    _last = target
    return Move(keys, detail) if keys else Move([], f"already at shadow level {target}")
