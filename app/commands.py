"""Wake phrase and GSPro key map.

Windows speech listens for these phrases, so each one must be a phrase it can recognise.
"""

from app.gspro_tree import SYNC_PHRASES
from app.grammar_words import NAV, TOGGLE

WAKE_PHRASES = ("hey caddie", "hey caddy")
LAUNCH_PHRASE = f"start application"  # starts GSPro if it is not running; handled in listener.py, not sent as keys
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
    Command(("aim point",), "f3", "Aim point", area="hitting_course"),
    Command(("shot cam", "shot camera"), "j", "Shot camera", area="Aim"),
    Command(("tee left",), "c", "Tee left", area="Aim", repeat=True),
    Command(("tee right",), "v", "Tee right", area="Aim", repeat=True),
    Command(("stop",), "", "Stop aim, zoom, tee, fly over, look left or right, a moving marker, or a slider being dragged", area="hitting_base"),
    Command((f"start application",), "", "Start GSPro if it is not running", area="Launch"),
    Command((f"{NAV} practice",), "", "From the GSPro home screen, open the practice screen", area="Launch"),
    Command(
        (f"{NAV} gspro practice range", "gspro practice range screen", "gspro range"),
        "",
        "From the GSPro practice screen, open the range",
        area="Launch",
    ),
    Command(
        (f"{NAV} gspro practice range now", "practice range now", "gspro range now"),
        "",
        "From the GSPro home screen, go straight to the range (skips the practice screen)",
        area="Launch",
    ),
    Command(
        (f"{NAV} on course practice now", "course practice now"),
        "",
        "From the GSPro home screen, go straight to on course practice (skips the practice screen)",
        area="Launch",
    ),
    Command(
        (f"{NAV} additional ranges now",),
        "",
        "From the GSPro home screen, go straight to additional ranges (skips the practice screen)",
        area="Launch",
    ),
    Command(("end round",), "", "Open the game menu and press END ROUND; then say confirm on the dialog", area="Launch"),
    Command(("confirm",), "", "On the end round dialog: confirm, which ends the round", area="Launch"),
    Command(("cancel",), "", "Closes the open game menu or end round dialog (on the end round dialog it keeps the round)", area="Launch"),
    Command(("back screen", "go back"), "", "Click BACK in the upper left of GSPro (say again for each level)", area="Launch"),  # primary, then aliases
    Command(("application exit",), "","Close GSpro and connectors (home screen only)", area="Launch"),
    Command((f"{NAV} on course practice",), "", "From the GSPro practice screen, open on course practice", area="Launch"),
    Command((f"{NAV} additional ranges",), "", "From the GSPro practice screen, open additional ranges", area="Launch"),
    Command((f"{NAV} play",), "", "From the GSPro home screen, press PLAY to open the course list", area="Launch"),
    Command((f"{NAV} challenges",), "", "From the GSPro home screen, press CHALLENGES", area="Launch"),
    Command((f"{NAV} tournaments",), "", "From the GSPro home screen, press TOURNAMENTS", area="Launch"),
    Command((f"{NAV} online match",), "", "From the GSPro home screen, press ONLINE MATCH", area="Launch"),
    Command(("open prefs",), "", "On the practice range, open the driving range panel (chevron)", area="Range"),
    Command(("change driving range distance", "change range distance"), "", "On the practice range, press the left end of the top slider and move right until stop", area="Range"),
    Command(("done",), "", "In the driving range panel, press Enter in the distance box (keeps the typed number)", area="Range"),
    Command((f"{TOGGLE} help",), "", "Show a red box over each button on this GSPro screen, or hide the boxes", area="Help"),
    Command(("help red",), "", "Help look: the red boxes (the default)", area="Help"),
    Command(("help blue",), "", "Help look: the gentle blue boxes", area="Help"),
    Command(("refresh help",), "", "Read the course rows again and redraw the help boxes (after the list changes)", area="Help"),
    Command(("place ball",), "", "Click the ball icon, then pick a point on the grid to place the ball", area="Ball"),
    Command(("place pin",), "", "Hold Shift and click the icon (it turns into a flag), then pick a point on the grid to place the pin", area="Ball"),
    Command(("alpha",), "", "Grid: cell A (column or row)", area="Grid"),
    Command(("bravo",), "", "Grid: cell B (column or row)", area="Grid"),
    Command(("charlie",), "", "Grid: cell C (column or row)", area="Grid"),
    Command(("delta",), "", "Grid: cell D (column or row)", area="Grid"),
    Command(("echo",), "", "Grid: cell E (column or row)", area="Grid"),
    Command(("foxtrot",), "", "Grid: cell F (column or row)", area="Grid"),
    Command(("golf",), "", "Grid: cell G (column or row)", area="Grid"),
    Command(("hotel",), "", "Grid: cell H (column or row)", area="Grid"),
    Command(("india",), "", "Grid: cell I (column or row)", area="Grid"),
    Command(("juliett",), "", "Grid: cell J (column or row)", area="Grid"),
    Command(("kilo",), "", "Grid: cell K (column or row)", area="Grid"),
    Command(("lima",), "", "Grid: cell L (column or row)", area="Grid"),
    Command(("mike",), "", "Grid: cell M (column or row)", area="Grid"),
    Command(("november",), "", "Grid: cell N (column or row)", area="Grid"),
    Command(("oscar",), "", "Grid: cell O (column or row)", area="Grid"),
    Command(("papa",), "", "Grid: cell P (column or row)", area="Grid"),
    Command(("quebec",), "", "Grid: cell Q (column or row)", area="Grid"),
    Command(("romeo",), "", "Grid: cell R (column or row)", area="Grid"),
    Command(("sierra",), "", "Grid: cell S (column or row)", area="Grid"),
    Command(("tango",), "", "Grid: cell T (column or row)", area="Grid"),
    Command(("uniform",), "", "Grid: cell U (column or row)", area="Grid"),
    Command(("victor",), "", "Grid: cell V (column or row)", area="Grid"),
    Command(("whiskey",), "", "Grid: cell W (column or row)", area="Grid"),
    Command(("xray",), "", "Grid: cell X (column or row)", area="Grid"),
    Command(("yankee",), "", "Grid: cell Y (column or row)", area="Grid"),
    Command(("zulu",), "", "Grid: cell Z (column or row)", area="Grid"),
    Command(("hide place",), "", "Hide the numbered grid", area="Place"),
    Command(("cancel place",), "", "Close the grid and click the ball icon again, which undoes the placement", area="Place"),
    Command(("redo",), "", "Place: take back the last letter. Say it again to go back one more", area="Place"),
    Command(("toggle map",), "", "Place: press S to change the mini map's size, without changing the app's flag (then sync map small or large if needed)", area="Place"),
    Command(("apply",), "", "In the driving range panel, click APPLY (closes the panel)", area="Range"),
    Command(("change max distance", "change max"), "", "In the driving range panel, press the Max Distance slider's left end and drag right until stop", area="Range"),
    Command(("type driving range distance",), "", "In the driving range panel, click the pencil on the distance, then say the digits; say done to finish", area="Range"),
    Command(("change min distance", "change min"), "", "In the driving range panel, press the Min Distance slider's left end and drag right until stop", area="Range"),
    Command(("change wind",), "", "Click the wind speed to open the wind panel", area="Wind"),
    Command(("change direction",), "", "Wind panel: press the Direction slider's left end and drag right until stop", area="Wind"),
    Command(("change strength",), "", "Wind panel: press the Strength slider's left end and drag right until stop", area="Wind"),
    Command(("change shots per one",), "", "In the driving range panel, click the 1 box under Shots Per", area="Range"),
    Command(("change shots per three",), "", "In the driving range panel, click the 3 box under Shots Per", area="Range"),
    Command(("change shots per five",), "", "In the driving range panel, click the 5 box under Shots Per", area="Range"),
    Command(("change shots per ten",), "", "In the driving range panel, click the 10 box under Shots Per", area="Range"),
    Command(("change shots per fifteen",), "", "In the driving range panel, click the 15 box under Shots Per", area="Range"),
    Command(("slide left",), "", "In the driving range panel, press where the pointer is and slide left until stop", area="Range"),
    Command(("slide right",), "", "In the driving range panel, press where the pointer is and slide right until stop", area="Range"),
    Command(("close prefs",), "", "In the driving range panel, click the chevron to close it", area="Range"),
    Command(("random on",), "", "In the driving range panel, click the randomizer arrows (a click toggles; the app cannot read the state)", area="Range"),
    Command(("random off",), "", "In the driving range panel, click the randomizer arrows (a click toggles; the app cannot read the state)", area="Range"),
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
    Command(("filter favorites",), "", "On course practice: show only your favorite courses", area="Launch"),
    Command(("clear filter",), "", "On course practice: clear the course search so the full list shows", area="Launch"),
    Command((f"use filter",), "", "On course practice: type a course name, one NATO letter at a time, to narrow the list", area="Course chooser"),
    Command(("stop filter",), "", "Stop typing the course filter; the list stays as it is", area="Course chooser"),
    Command(("show punctuation",), "", "While typing the filter: the list shows the punctuation words instead of the NATO letters", area="Course chooser"),
    Command(("show letters",), "", "While typing the filter: the list shows the NATO letters again", area="Course chooser"),
    Command(("backspace",), "", "While filtering: delete the last letter, in case it was misheard", area="Course chooser"),
    Command(("download row one",), "", "Download the course in row 1 (not if it is already installed)", area="Course chooser"),
    Command(("download row two",), "", "Download the course in row 2 (not if it is already installed)", area="Course chooser"),
    Command(("download row three",), "", "Download the course in row 3 (not if it is already installed)", area="Course chooser"),
    Command(("download row four",), "", "Download the course in row 4 (not if it is already installed)", area="Course chooser"),
    Command(("download row five",), "", "Download the course in row 5 (not if it is already installed)", area="Course chooser"),
    Command(("download row six",), "", "Download the course in row 6 (not if it is already installed)", area="Course chooser"),
    Command(("download row seven",), "", "Download the course in row 7 (not if it is already installed)", area="Course chooser"),
    Command(("download row eight",), "", "Download the course in row 8 (not if it is already installed)", area="Course chooser"),
    Command(("download row nine",), "", "Download the course in row 9 (not if it is already installed)", area="Course chooser"),
    Command(("download row one now",), "", "Download the course in row 1 (same as download row one; \"now\" is optional)", area="Course chooser"),
    Command(("download row two now",), "", "Download the course in row 2 (same as download row two; \"now\" is optional)", area="Course chooser"),
    Command(("download row three now",), "", "Download the course in row 3 (same as download row three; \"now\" is optional)", area="Course chooser"),
    Command(("download row four now",), "", "Download the course in row 4 (same as download row four; \"now\" is optional)", area="Course chooser"),
    Command(("download row five now",), "", "Download the course in row 5 (same as download row five; \"now\" is optional)", area="Course chooser"),
    Command(("download row six now",), "", "Download the course in row 6 (same as download row six; \"now\" is optional)", area="Course chooser"),
    Command(("download row seven now",), "", "Download the course in row 7 (same as download row seven; \"now\" is optional)", area="Course chooser"),
    Command(("download row eight now",), "", "Download the course in row 8 (same as download row eight; \"now\" is optional)", area="Course chooser"),
    Command(("download row nine now",), "", "Download the course in row 9 (same as download row nine; \"now\" is optional)", area="Course chooser"),
    Command(("play row one",), "", "Play the installed course in row 1 (not if it still shows Download)", area="Course chooser"),
    Command(("play row two",), "", "Play the installed course in row 2 (not if it still shows Download)", area="Course chooser"),
    Command(("play row three",), "", "Play the installed course in row 3 (not if it still shows Download)", area="Course chooser"),
    Command(("play row four",), "", "Play the installed course in row 4 (not if it still shows Download)", area="Course chooser"),
    Command(("play row five",), "", "Play the installed course in row 5 (not if it still shows Download)", area="Course chooser"),
    Command(("play row six",), "", "Play the installed course in row 6 (not if it still shows Download)", area="Course chooser"),
    Command(("play row seven",), "", "Play the installed course in row 7 (not if it still shows Download)", area="Course chooser"),
    Command(("play row eight",), "", "Play the installed course in row 8 (not if it still shows Download)", area="Course chooser"),
    Command(("play row nine",), "", "Play the installed course in row 9 (not if it still shows Download)", area="Course chooser"),
    Command(("play row one now",), "", "Play the installed course in row 1, then press PLAY on round settings", area="Course chooser"),
    Command(("play row two now",), "", "Play the installed course in row 2, then press PLAY on round settings", area="Course chooser"),
    Command(("play row three now",), "", "Play the installed course in row 3, then press PLAY on round settings", area="Course chooser"),
    Command(("play row four now",), "", "Play the installed course in row 4, then press PLAY on round settings", area="Course chooser"),
    Command(("play row five now",), "", "Play the installed course in row 5, then press PLAY on round settings", area="Course chooser"),
    Command(("play row six now",), "", "Play the installed course in row 6, then press PLAY on round settings", area="Course chooser"),
    Command(("play row seven now",), "", "Play the installed course in row 7, then press PLAY on round settings", area="Course chooser"),
    Command(("play row eight now",), "", "Play the installed course in row 8, then press PLAY on round settings", area="Course chooser"),
    Command(("play row nine now",), "", "Play the installed course in row 9, then press PLAY on round settings", area="Course chooser"),
    Command((f"{TOGGLE} favorite row one",), "", "Toggle the favourite heart of row 1 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row two",), "", "Toggle the favourite heart of row 2 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row three",), "", "Toggle the favourite heart of row 3 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row four",), "", "Toggle the favourite heart of row 4 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row five",), "", "Toggle the favourite heart of row 5 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row six",), "", "Toggle the favourite heart of row 6 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row seven",), "", "Toggle the favourite heart of row 7 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row eight",), "", "Toggle the favourite heart of row 8 (adds or removes it from your favourites)", area="Course chooser"),
    Command((f"{TOGGLE} favorite row nine",), "", "Toggle the favourite heart of row 9 (adds or removes it from your favourites)", area="Course chooser"),
    Command(("show notes one",), "", "Open the show notes panel for row 1 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes two",), "", "Open the show notes panel for row 2 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes three",), "", "Open the show notes panel for row 3 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes four",), "", "Open the show notes panel for row 4 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes five",), "", "Open the show notes panel for row 5 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes six",), "", "Open the show notes panel for row 6 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes seven",), "", "Open the show notes panel for row 7 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes eight",), "", "Open the show notes panel for row 8 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("show notes nine",), "", "Open the show notes panel for row 9 (the icon left of the favourite heart)", area="Course chooser"),
    Command(("read more",), "", "In the show notes panel: open the course description", area="Course chooser"),
    Command(("latest scores",), "", "In the show notes panel: open the latest scores for that course", area="Course chooser"),
    Command(("play course now",), "", "In the show notes panel: press Play, then PLAY on round settings so the round starts", area="Course chooser"),
    Command(("space",), "", "Filter: type a space", area="Filter entry"),
    Command(("underscore",), "", "Filter: type an underscore (_)", area="Filter entry"),
    Command(("dash",), "", "Filter: type a dash (-)", area="Filter entry"),
    Command(("comma",), "", "Filter: type a comma (,)", area="Filter entry"),
    Command(("period",), "", "Filter: type a period (.)", area="Filter entry"),
    Command(("parenthesis",), "", "Filter: type a bracket; the first is ( and the next is )", area="Filter entry"),
    Command(("number sign",), "", "Filter: type a number sign (#)", area="Filter entry"),
    Command(("plus sign",), "", "Filter: type a plus sign (+)", area="Filter entry"),
    Command((f"{TOGGLE} listening",), "", "Pause voice commands, or resume them. While paused, only 'toggle listening' is heard", area="Voice"),
    Command(("filter installed",), "", "On course practice: show the whole installed list again", area="Launch"),
    Command(("filter all",), "", "On course practice: show every course, installed or not", area="Course chooser"),
    Command(("filter trending",), "", "On course practice: show the trending courses", area="Course chooser"),
    Command(("show game menu",), "", "While playing: open the game menu (hamburger, upper right)", area="Launch"),
    Command(("debug press",), "", "Debug: one test press on the practice range card", area="Debug"),
    Command((f"{TOGGLE} hand",), "n", "Switch hand (left or right)", area="hitting_base"),
    Command(("club up",), "i", "Next club toward the putter", area="Club"),
    Command(("club down",), "k", "Next club toward the driver", area="Club"),
    Command(("club putter",), "u", "Jump to the putter", area="Club", heard=False),
    Command(("zoom in",), "q", "Zoom in", area="Map", repeat=True, hold=True),
    Command(("zoom out",), "w", "Zoom out", area="Map", repeat=True, hold=True),
    Command((f"{TOGGLE} map", "mini map", "shrink map"), "s", "Toggle the mini map (S): expand or shrink", area="Map"),
    Command(("sync map small",), "", "Tell the app the mini map is small (no keys, no clicks)", area="Map"),
    Command(("sync map large",), "", "Tell the app the mini map is large (no keys, no clicks)", area="Map"),
    Command((f"{TOGGLE} free flight", f"{TOGGLE} flight"), "", "On the course screen, turn free flight on (F5), or off again (F5)", area="Map"),
    Command(("place marker",), "", "On the course screen, drop a marker at the center of the mini map, or where the moved marker is", area="Map"),
    Command(("left",), "", "Marker panel: move the marker left until stop", area="Marker"),
    Command(("right",), "", "Marker panel: move the marker right until stop", area="Marker"),
    Command(("up",), "", "Marker panel: move the marker up until stop", area="Marker"),
    Command(("down",), "", "Marker panel: move the marker down until stop", area="Marker"),
    Command(("change hole",), "", "Course practice: click the flag icon at the top left to open the change hole panel", area="Course practice"),
    *(Command((word,), "", f"Hole panel: click hole {number} (the cancel closes the panel)", area="Hole")
      for number, word in ((10, "ten"), (11, "eleven"), (12, "twelve"), (13, "thirteen"), (14, "fourteen"),
                           (15, "fifteen"), (16, "sixteen"), (17, "seventeen"), (18, "eighteen"))),
    Command(("cancel marker",), "", "Marker panel: let go of the button where the marker is, make the map small again if place marker made it large, and leave the panel", area="Marker"),
    Command(("fly over",), "o", "Flyover", area="View", closes=True, stops=True),
    Command((f"{TOGGLE} heat map",), "y", "Toggle the heat map", area="View"),
    Command((f"{TOGGLE} scorecard",), "t", "Toggle the scorecard", area="View"),
    Command(("close",), "", "Press the last toggle again", area="View"),
    Command((f"{TOGGLE} green grid",), "g", "Toggle the green grid", area="View"),
    Command((f"{TOGGLE} pin", "show pin", "pin"), "p", "Toggle the pin indicator", area="View"),
    Command(("range finder",), "r", "Range finder", area="View", closes=True),
    Command(("look left",), "left", "Slide range finder left", area="View", hold=True),
    Command(("look right",), "right", "Slide range finder right", area="View", hold=True),
    Command((f"{TOGGLE} ui",), "h", "Hide the interface, or show it again (Esc) if it is hidden", area="hitting_base"),
    Command(("open menu",), "esc", "Show the interface", area="hitting_base"),
    Command(("clear tracer",), "f1", "Clear tracers", area="Range"),
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
    Command(("shadow one",), "", "Shadow level 1 (lightest); the first time, or the same level twice, starts from the lightest", area="Visual / System", heard=False),
    Command(("shadow two",), "", "Shadow level 2", area="Visual / System", heard=False),
    Command(("shadow three",), "", "Shadow level 3", area="Visual / System", heard=False),
    Command(("shadow four",), "", "Shadow level 4", area="Visual / System", heard=False),
    Command(("shadow five",), "", "Shadow level 5 (deepest)", area="Visual / System", heard=False),
    Command((f"{TOGGLE} fullscreen",), "f11", "Toggle GSPro fullscreen (F11)", area="Visual / System"),
    Command(("fast forward", "faster"), "space", "Fast forward", area="Visual / System"),
    Command(("sound off",), "minus", "Sound off", area="Visual / System", wired=False),
    Command(("sound on",), "add", "Sound on", area="Visual / System", wired=False),
    Command((f"{TOGGLE} keyboard",), "tab", "Toggle the keyboard shortcuts (Tab), in GSPro", area="Always on"),
    Command(("console short",), "f8", "Short console", area="Visual / System", wired=False),
    Command(("console tall",), "f9", "Tall console", area="Visual / System", wired=False),
)

# "sync to <screen>" rows: set the app's screen when it has drifted out of sync with GSPro.
# Each sync phrase has a secondary without the word "screen" at the end, and some have extra secondaries.
_EXTRA_SYNC_ALIASES: dict[str, tuple[str, ...]] = {
    "sync to gspro practice range screen": ("sync to practice range", "sync to gspro range"),
    "sync to course practice screen": ("sync to practice course",),
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


def repeat_variants(phrase: str) -> tuple[str, ...]:
    """The numbered and continue forms of a repeat command, such as "zoom in five" or "zoom in continue".
    Empty for any other phrase. The grammar listens for these; they are not shown in the tables."""
    for row in ROWS:
        if row.repeat and phrase in row.phrases:
            return tuple(f"{phrase} {word}" for word in (*_NUMBER_WORDS, "continue"))
    return ()


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


_REPEAT_PRIMARIES: frozenset[str] = frozenset(row.phrases[0] for row in ROWS if row.repeat)


def shown(phrase: str) -> str:
    """The phrase as a table shows it. A repeat command gets (#), since a number can be said after it."""
    return f"{phrase} (#)" if primary(phrase) in _REPEAT_PRIMARIES else phrase

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
    """The course name said after "play course", and whether "now" was said at the end."""
    cleaned = spoken_text(text)
    index = cleaned.find(COURSE_PHRASE)
    rest = cleaned[index + len(COURSE_PHRASE):].strip() if index >= 0 else ""
    if rest == "course" or rest.startswith("course "):
        rest = rest[len("course"):].strip()  # the "course" in "play course <name>"
    then_now = rest == "now" or rest.endswith(" now")
    if then_now:
        rest = rest[: -len("now")].strip()
    return rest, then_now


def course_name(text: str) -> str:
    """The words said after "play course", without a trailing "now"."""
    return parse_course(text)[0]


def contains_wake(text: str) -> bool:
    cleaned = spoken_text(text)
    return any(phrase in cleaned for phrase in WAKE_PHRASES)


def match_command(text: str) -> str | None:
    """Longest known phrase contained in a recognition result, as its primary phrase."""
    from app.bag import spoken_phrases
    from app.gspro_courses import course_phrases
    from app.shadows import spoken_phrases as shadow_phrases

    cleaned = spoken_text(text)
    found = [phrase for phrase in (*COMMANDS, *spoken_phrases(), *shadow_phrases(), *course_phrases()) if phrase in cleaned]
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
    import time

    import pydirectinput

    index = 0
    while index < len(keys):
        key = keys[index]
        count = 1
        while index + count < len(keys) and keys[index + count] == key:
            count += 1
        if "+" in key:  # a held modifier, written "shift+," (see app/shadows.py)
            modifier, _, letter = key.partition("+")
            for _ in range(count):
                press_keys((modifier, letter))
                time.sleep(0.08)
        else:
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
