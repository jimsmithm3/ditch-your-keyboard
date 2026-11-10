"""Wake phrase and GSPro key map.

The small Vosk model has no word "gspraudio" (lookup returns -1), so that
phrase can never match. "hey caddie" / "hey caddy" are in the lexicon.
Spoken phrases below are words that model does contain.
"""

from app.gspro_tree import SYNC_PHRASES

WAKE_PHRASES = ("hey caddie", "hey caddy")
LAUNCH_PHRASE = "please play golf"  # starts GSPro if it is not running; handled in listener.py, not sent as keys
DEBUG_PHRASE = "debug press"  # one test press per command, for click debugging; handled in listener.py
COURSE_PHRASE = "play"  # "play <name>" types the name in GSPro's course search; handled in listener.py
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
    Command(("stop",), "", "Stop aim, zoom, tee, flyover, a moving marker, or a slider being dragged", area="Aim"),
    Command(("please play golf",), "", "Start GSPro if it is not running", area="Launch"),
    Command(("practice screen",), "", "From the GSPro home screen, open the practice screen", area="Launch"),
    Command(
        ("gspro practice range", "gspro practice range screen", "gspro range"),
        "",
        "From the GSPro practice screen, open the range",
        area="Launch",
    ),
    Command(
        ("gspro practice range now", "practice range now", "gspro range now"),
        "",
        "From the GSPro home screen, go straight to the range (skips the practice screen)",
        area="Launch",
    ),
    Command(
        ("on course practice now", "course practice now"),
        "",
        "From the GSPro home screen, go straight to on course practice (skips the practice screen)",
        area="Launch",
    ),
    Command(
        ("additional ranges now",),
        "",
        "From the GSPro home screen, go straight to additional ranges (skips the practice screen)",
        area="Launch",
    ),
    Command(("end round",), "", "From the GSPro range, open the menu and end the round", area="Launch"),
    Command(("back screen", "go back"), "", "Click BACK in the upper left of GSPro (say again for each level)", area="Launch"),  # primary, then aliases
    Command(("home screen",), "", "Click BACK until GSPro is at the home screen", area="Launch"),
    Command(("please exit golf", "please stop gspro"), "", "Close GSpro and connectors (home screen; then say confirm exit)", area="Launch"),
    Command(("confirm exit",), "", "Confirm closing GSpro, within 8 seconds of please exit golf", area="Launch"),
    Command(("on course practice",), "", "From the GSPro practice screen, open on course practice", area="Launch"),
    Command(("additional ranges",), "", "From the GSPro practice screen, open additional ranges", area="Launch"),
    Command(("play screen",), "", "From the GSPro home screen, press PLAY to open the course list", area="Launch"),
    Command(("now",), "", "On round settings, press PLAY to start the course", area="Launch"),
    Command(("open preferences",), "", "On the practice range, open the driving range panel (chevron)", area="Range"),
    Command(("change driving range distance", "change range distance"), "", "On the practice range, click the pencil on Driving Range Distance, then say the digits", area="Range"),
    Command(("done",), "", "In the driving range panel, press Enter in the distance box (keeps the typed number)", area="Range"),
    Command(("apply",), "", "In the driving range panel, click APPLY (closes the panel)", area="Range"),
    Command(("change max distance", "change max"), "", "In the driving range panel, press the Max Distance slider's left end and drag right until stop", area="Range"),
    Command(("change min distance", "change min"), "", "In the driving range panel, press the Min Distance slider's left end and drag right until stop", area="Range"),
    Command(("change shots per one",), "", "In the driving range panel, click the 1 box under Shots Per", area="Range"),
    Command(("change shots per three",), "", "In the driving range panel, click the 3 box under Shots Per", area="Range"),
    Command(("change shots per five",), "", "In the driving range panel, click the 5 box under Shots Per", area="Range"),
    Command(("change shots per ten",), "", "In the driving range panel, click the 10 box under Shots Per", area="Range"),
    Command(("change shots per fifteen",), "", "In the driving range panel, click the 15 box under Shots Per", area="Range"),
    Command(("slide left",), "", "In the driving range panel, press where the pointer is and slide left at a third of the slider speed until stop", area="Range"),
    Command(("slide right",), "", "In the driving range panel, press where the pointer is and slide right at a third of the slider speed until stop", area="Range"),
    Command(("close preferences",), "", "In the driving range panel, click the chevron to close it", area="Range"),
    Command(("randomizer on",), "", "In the driving range panel, click the randomizer arrows (a click toggles; the app cannot read the state)", area="Range"),
    Command(("randomizer off",), "", "In the driving range panel, click the randomizer arrows (a click toggles; the app cannot read the state)", area="Range"),
    # One row for the ten digit words. Each word types its own digit (DIGIT_KEYS below).
    Command(
        ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
        "",
        "Say each number you want out loud; each one is typed in the distance box",
        area="Range",
    ),
    Command(("players tab",), "", "On round settings, switch to the Players tab", area="Launch"),
    Command(("match tab",), "", "On round settings, switch to the Match tab", area="Launch"),
    Command(("holes tab",), "", "On round settings, switch to the Holes tab", area="Launch"),
    Command(("play course",), "", "On round settings, press PLAY for the course that is set up", area="Launch"),
    Command(("show favorites",), "", "On course practice: show only your favorite courses", area="Launch"),
    Command(("clear course",), "", "On course practice: clear the course search so the full list shows", area="Launch"),
    Command(("stop listening",), "", "Pause voice commands. Only 'start listening' is heard until then", area="Voice"),
    Command(("start listening",), "", "Resume voice commands", area="Voice"),
    Command(("show installed",), "", "On course practice: show the whole installed list again", area="Launch"),
    Command(("show menu",), "", "While playing: open the game menu (hamburger, upper right)", area="Launch"),
    Command(("cancel menu",), "", "While playing: close the game menu", area="Launch"),
    Command(("debug press",), "", "Debug: one test press on the practice range card", area="Debug"),
    Command(("switch hand",), "n", "Switch hand", area="Aim", wired=False),
    Command(("club up",), "i", "Next club toward the putter", area="Club", heard=False),
    Command(("club down",), "k", "Next club toward the driver", area="Club", heard=False),
    Command(("reset club",), "k", "Back to the driver", area="Club", heard=False),
    Command(("putter",), "u", "Jump to the putter", area="Club", heard=False),
    Command(("zoom in",), "q", "Zoom in", area="Map", repeat=True, hold=True),
    Command(("zoom out",), "w", "Zoom out", area="Map", repeat=True, hold=True),
    Command(("expand map", "mini map", "shrink map"), "s", "Toggle the mini map (S): expand or shrink", area="Map", closes=True),
    Command(("map mode start",), "", "On the course screen, hold the mouse button on the mini map center (distances show)", area="Map"),
    Command(("map mode end",), "", "Let go of the mouse button and leave map mode", area="Map"),
    Command(("free flight mode start", "flight mode start"), "", "On the course screen, turn on free flight (F5)", area="Map"),
    Command(("free flight mode end", "flight mode end"), "", "Turn free flight off (F5 again)", area="Map"),
    Command(("marker place",), "", "On the course screen, drop a marker at the center of the mini map, or where the moved marker is", area="Map"),
    Command(("marker left",), "", "On the course screen, move the marker left until stop", area="Map"),
    Command(("marker right",), "", "On the course screen, move the marker right until stop", area="Map"),
    Command(("marker up",), "", "On the course screen, move the marker up until stop", area="Map"),
    Command(("marker down",), "", "On the course screen, move the marker down until stop", area="Map"),
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

# "sync to <screen>" rows: set the app's screen when it has drifted out of sync with GSPro.
# Each sync phrase has a secondary without the word "screen" at the end, and some have extra secondaries.
_EXTRA_SYNC_ALIASES: dict[str, tuple[str, ...]] = {
    "sync to gspro practice range screen": ("sync to practice range", "sync to gspro range"),
}
_SYNC_ROWS = tuple(
    Command(
        (phrase, phrase.removesuffix(" screen"), *_EXTRA_SYNC_ALIASES.get(phrase, ())),
        "",
        f"Tell the app GSPro is on the {SYNC_PHRASES[phrase]} screen (no clicks)",
        area="Launch",
    )
    for phrase in SYNC_PHRASES
)
ROWS = ROWS + _SYNC_ROWS

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

# Each digit word types its digit. They share one row, but each word is its own command, so the
# digit words are not aliases of each other.
DIGIT_KEYS: dict[str, str] = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
COMMANDS.update(DIGIT_KEYS)

# A command row lists its primary phrase first, then aliases. Aliases exist only so the speech
# grammar hears them; everything else (sequences, tables, status) uses the primary.
_PRIMARY: dict[str, str] = {
    phrase: row.phrases[0] for row in ROWS if row.phrases[0] not in DIGIT_KEYS for phrase in row.phrases
}
_ALIASES: dict[str, tuple[str, ...]] = {row.phrases[0]: row.phrases[1:] for row in ROWS if row.phrases[0] not in DIGIT_KEYS}


def primary(phrase: str) -> str:
    """The primary phrase for any phrase. An alias gives the primary of its row."""
    return _PRIMARY.get(phrase, phrase)


def aliases_of(primary_phrase: str) -> tuple[str, ...]:
    """The alias phrases of a primary. For grammar matching only."""
    return _ALIASES.get(primary_phrase, ())

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


def parse_course(text: str) -> tuple[str, bool]:
    """The course name said after "play", and whether "now" was said at the end."""
    cleaned = spoken_text(text)
    index = cleaned.find(COURSE_PHRASE)
    rest = cleaned[index + len(COURSE_PHRASE):].strip() if index >= 0 else ""
    then_now = rest == "now" or rest.endswith(" now")
    if then_now:
        rest = rest[: -len("now")].strip()
    return rest, then_now


def course_name(text: str) -> str:
    """The words said after "play", without a trailing "now"."""
    return parse_course(text)[0]


def contains_wake(text: str) -> bool:
    cleaned = spoken_text(text)
    return any(phrase in cleaned for phrase in WAKE_PHRASES)


def match_command(text: str) -> str | None:
    """Longest known phrase contained in a recognition result, as its primary phrase."""
    from app.bag import spoken_phrases
    from app.gspro_courses import course_phrases

    cleaned = spoken_text(text)
    found = [phrase for phrase in (*COMMANDS, *spoken_phrases(), *course_phrases()) if phrase in cleaned]
    if not found:
        return None
    return primary(max(found, key=len))


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
