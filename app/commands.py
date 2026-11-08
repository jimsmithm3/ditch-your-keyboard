"""Wake phrase and GSPro key map.

The small Vosk model has no word "gspraudio" (lookup returns -1), so that
phrase can never match. "hey caddie" / "hey caddy" are in the lexicon.
Spoken phrases below are words that model does contain.
"""

WAKE_PHRASES = ("hey caddie", "hey caddy")
LAUNCH_PHRASE = "play golf"  # starts GSPro if it is not running; handled in listener.py, not sent as keys
DEBUG_PHRASE = "debug press"  # one test press per command, for click debugging; handled in listener.py
ARM_SECONDS = 5.0

class Command:
    """One GSPro action. heard=False is handled by the bag, not COMMANDS."""

    def __init__(
        self,
        phrases: tuple[str, ...],
        keys: str | tuple[str, ...],
        description: str,
        *,
        wired: bool = True,
        heard: bool = True,
        area: str,
        repeat: bool = False,
        hold: bool = False,
        closes: bool = False,
        stops: bool = False,
    ) -> None:
        self.phrases = phrases
        self.keys = keys
        self.description = description
        self.area = area
        self.wired = wired
        self.heard = heard
        self.repeat = repeat
        self.hold = hold
        self.closes = closes
        self.stops = stops


# wired=False is shown in the commands dialog and is not recognized.
# heard=False is a bag action (club step or putter) and is not in COMMANDS.
ROWS: tuple[Command, ...] = (
    Command(("aim left",), "left", "Aim left", area="Aim", repeat=True, hold=True),
    Command(("aim right",), "right", "Aim right", area="Aim", repeat=True, hold=True),
    Command(("aim forward", "aim up"), "up", "Aim forward", area="Aim"),
    Command(("aim back", "aim down"), "down", "Aim back", area="Aim"),
    Command(("reset aim",), "a", "Reset aim", area="Aim"),
    Command(("aim point",), "f3", "Aim point", area="Aim", wired=False),
    Command(("shot cam", "shot camera"), "j", "Shot camera", area="Aim"),
    Command(("tee left",), "c", "Tee left", area="Aim", repeat=True),
    Command(("tee right",), "v", "Tee right", area="Aim", repeat=True),
    Command(("stop",), "", "Stop aim, zoom, tee, or flyover", area="Aim"),
    Command(("play golf",), "", "Start GSPro if it is not running", area="Launch"),
    Command(("practice screen",), "", "From the GSPro home screen, open the practice screen", area="Launch"),
    Command(
        ("gspro practice range screen", "gspro practice range"),
        "",
        "From the GSPro practice screen, open the range",
        area="Launch",
    ),
    Command(("go to range",), "", "From the GSPro home screen, open the range", area="Launch"),
    Command(("end round",), "", "From the GSPro range, open the menu and end the round", area="Launch"),
    Command(("go back", "back screen"), "", "Click BACK in the upper left of GSPro (say again for each level)", area="Launch"),
    Command(("home screen",), "", "Click BACK until GSPro is at the home screen", area="Launch"),
    Command(("debug press",), "", "Debug: one test press on the practice range card", area="Debug"),
    Command(("switch hand",), "n", "Switch hand", area="Aim", wired=False),
    Command(("club up",), "i", "Next club toward the putter", area="Club", heard=False),
    Command(("club down",), "k", "Next club toward the driver", area="Club", heard=False),
    Command(("reset club",), "k", "Back to the driver", area="Club", heard=False),
    Command(("putter",), "u", "Jump to the putter", area="Club", heard=False),
    Command(("zoom in",), "q", "Zoom in", area="Map", repeat=True, hold=True),
    Command(("zoom out",), "w", "Zoom out", area="Map", repeat=True, hold=True),
    Command(("expand map", "mini map"), "s", "Expand map", area="Map", closes=True),
    Command(("flyover",), "o", "Flyover", area="View", closes=True, stops=True),
    Command(("heat map",), "y", "Heat map", area="View"),
    Command(("scorecard",), "t", "Scorecard", area="View", closes=True),
    Command(("close",), "", "Press the last toggle again", area="View"),
    Command(("green grid",), "g", "Green grid", area="View"),
    Command(("pin indicator", "show pin", "pin"), "p", "Pin indicator", area="View"),
    Command(("range finder",), "r", "Range finder", area="View", closes=True),
    Command(("move left",), "left", "Slide range finder left", area="View", hold=True),
    Command(("move right",), "right", "Slide range finder right", area="View", hold=True),
    Command(("hide ui", "hide interface"), "h", "Hide the interface", area="View"),
    Command(("show ui", "open menu"), "esc", "Show the interface", area="View"),
    Command(("clear tracer",), "f1", "Clear tracers", area="View", wired=False),
    Command(("mulligan",), ("ctrl", "m"), "Mulligan", area="Mulligan"),
    Command(("cam go to ball",), "5", "Camera to the ball", area="Camera", wired=False),
    Command(("cam fly to ball",), "6", "Fly the camera to the ball", area="Camera", wired=False),
    Command(("free look",), "f5", "Free look", area="Camera", wired=False),
    Command(("cam clip",), "b", "Clip the camera", area="Camera", wired=False),
    Command(("go to ball",), "8", "Go to the ball (Practice Only)", area="Practice"),
    Command(("previous hole",), "9", "Previous hole (Practice Only)", area="Practice"),
    Command(("next hole",), "0", "Next hole (Practice Only)", area="Practice"),
    Command(("vert dots",), "d", "Vertical dots", area="Visual / System", wired=False),
    Command(("lighting",), "l", "Cycle lighting", area="Visual / System", wired=False),
    Command(("3d grass",), "z", "3D grass", area="Visual / System", wired=False),
    Command(("fps",), "f", "FPS counter", area="Visual / System", wired=False),
    Command(("shadow down",), ("shift", ","), "Lighter shadows", area="Visual / System", wired=False),
    Command(("shadow up",), ("shift", "."), "Deeper shadows", area="Visual / System", wired=False),
    Command(("fullscreen",), "f11", "Fullscreen", area="Visual / System", wired=False),
    Command(("fast forward", "faster"), "space", "Fast forward", area="Visual / System"),
    Command(("sound off",), "minus", "Sound off", area="Visual / System", wired=False),
    Command(("sound on",), "add", "Sound on", area="Visual / System", wired=False),
    Command(("keyboard toggle",), "tab", "Keyboard shortcuts", area="Visual / System", wired=False),
    Command(("console short",), "f8", "Short console", area="Visual / System", wired=False),
    Command(("console tall",), "f9", "Tall console", area="Visual / System", wired=False),
)

_NUMBER_WORDS = (
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
)
_COUNT = {word: number for number, word in enumerate(_NUMBER_WORDS, start=1)}


def _heard_phrases(row: Command) -> tuple[str, ...]:
    if not row.repeat:
        return row.phrases
    return tuple(
        phrase if not word else f"{phrase} {word}"
        for phrase in row.phrases
        for word in ("", *_NUMBER_WORDS, "continue")
    )


COMMANDS: dict[str, str | tuple[str, ...]] = {
    phrase: row.keys for row in ROWS if row.wired and row.heard for phrase in _heard_phrases(row)
}

CLOSABLE: dict[str, str | tuple[str, ...]] = {
    phrase: row.keys for row in ROWS if row.wired and row.closes for phrase in row.phrases
}

STOPPABLE: dict[str, str | tuple[str, ...]] = {
    phrase: row.keys for row in ROWS if row.wired and row.stops for phrase in row.phrases
}

_KEY_TEXT = {
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "space": "Space",
    "esc": "Esc",
    "ctrl": "Ctrl",
    "shift": "Shift",
    "tab": "Tab",
    "minus": "−",
    "add": "+",
}


def spoken_text(text: str) -> str:
    """Drop the recognizer's unknown token so it cannot hide a real phrase."""
    return " ".join(part for part in text.split() if part != "[unk]").strip()


def contains_wake(text: str) -> bool:
    cleaned = spoken_text(text)
    return any(phrase in cleaned for phrase in WAKE_PHRASES)


def match_command(text: str) -> str | None:
    """Longest known phrase contained in a recognition result."""
    from app.bag import spoken_phrases

    cleaned = spoken_text(text)
    found = [phrase for phrase in (*COMMANDS, *spoken_phrases()) if phrase in cleaned]
    if not found:
        return None
    return max(found, key=len)


def voice_text(command: Command) -> str:
    if command.hold and not command.repeat:
        return " / ".join(f"{phrase} (until stop)" for phrase in command.phrases)
    if not command.repeat:
        return " / ".join(command.phrases)
    return " / ".join(f"{phrase} (one to ten, or continue)" for phrase in command.phrases)


def is_continue(phrase: str) -> bool:
    """True when the phrase should keep going until stop."""
    for row in ROWS:
        if not row.repeat or not row.wired:
            continue
        for base in row.phrases:
            if phrase == f"{base} continue":
                return True
    return False


def holds_key(phrase: str) -> bool:
    """True when the phrase should keep the key down until stop."""
    for row in ROWS:
        if not row.wired or not row.hold:
            continue
        if row.repeat:
            for base in row.phrases:
                if phrase == f"{base} continue":
                    return True
        elif phrase in row.phrases:
            return True
    return False


def repeat_count(phrase: str) -> int:
    """How many times to press. A bare phrase is once."""
    for row in ROWS:
        if not row.repeat:
            continue
        for base in row.phrases:
            if phrase == base:
                return 1
            prefix = f"{base} "
            if phrase.startswith(prefix):
                return _COUNT.get(phrase[len(prefix):], 1)
    return 1


def key_label(binding: str | tuple[str, ...]) -> str:
    if isinstance(binding, tuple):
        return "+".join(binding)
    return binding


def key_text(binding: str | tuple[str, ...]) -> str:
    """Keystroke as shown in the commands dialog."""

    def one(key: str) -> str:
        if not key:
            return "—"
        if key in _KEY_TEXT:
            return _KEY_TEXT[key]
        if key.startswith("f") and key[1:].isdigit():
            return key.upper()
        if len(key) == 1:
            return key.upper()
        return key

    if isinstance(binding, tuple):
        return "+".join(one(key) for key in binding)
    return one(binding)


def press_times(keys: list[str]) -> None:
    """Repeat a run of the same key slowly enough for GSPro to see each one."""
    import pydirectinput

    index = 0
    while index < len(keys):
        key = keys[index]
        count = 1
        while index + count < len(keys) and keys[index + count] == key:
            count += 1
        pydirectinput.press(key, presses=count, interval=0.08)
        index += count


def hold_key(key: str) -> None:
    import pydirectinput

    pydirectinput.keyDown(key)


def release_key(key: str) -> None:
    import pydirectinput

    pydirectinput.keyUp(key)


def press_keys(binding: str | tuple[str, ...]) -> None:
    import pydirectinput

    if isinstance(binding, str):
        pydirectinput.press(binding)
        return
    modifiers, key = binding[:-1], binding[-1]
    for modifier in modifiers:
        pydirectinput.keyDown(modifier)
    try:
        pydirectinput.press(key)
    finally:
        for modifier in reversed(modifiers):
            pydirectinput.keyUp(modifier)
