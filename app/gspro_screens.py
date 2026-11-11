"""Screen records for GSPro voice commands. These drive the speech grammar.

Each screen says what it can do in one place:
  trans   the transitions out of it: what you say, the screen it lands on, and the sequence that runs it
  groups  the property groups it has (Back, Menu, Club, and so on), from GROUPS below

Speech grammar (recognizer_setup): GLOBAL phrases are always listening. Everything else is heard
only on the screen or panel that claims it. Each screen's trans and groups form its own grammar, switched on while GSPro is on
that screen. check() compares the records with gspro_tree.py and commands.py.
"""

from dataclasses import dataclass

from app.commands import DIGIT_KEYS, ROWS, aliases_of
from app.gspro_tree import SCREENS as TREE_SCREENS
from app.gspro_tree import SYNC_PHRASES


@dataclass(frozen=True)
class Trans:
    phrase: str  # what you say; "play <course>" stands for any course name
    goes_to: str  # the screen key it lands on
    sequence: str = ""  # the sequence that runs it; empty until one exists
    aliases: tuple[str, ...] = ()  # secondary phrases for the same transition


@dataclass(frozen=True)
class Screen:
    key: str
    name: str
    parent: str | None  # the screen "go back" returns to; None for home
    trans: tuple[Trans, ...] = ()
    groups: tuple[str, ...] = ()
    note: str = ""  # a second line on the tree box, to say what the screen is for


# Property and capability groups: the phrases each group holds. A screen has a group when
# it lists the group's name in its groups.
GROUPS: dict[str, tuple[str, ...]] = {
    "Ball": ("place ball",),  # course practice and course play: the ball icon, then a grid point
    "Exit": ("please exit golf", "confirm exit"),  # home screen only; exit takes two steps so it is not an accident
    "Back": ("back screen",),
    "Range": ("open preferences", "close preferences"),  # practice range: the driving range panel (see PANELS); close is here too, so it is heard after the panel memory drifts
    "Tabs": ("players tab", "match tab", "holes tab"),  # round settings: the three tabs along the top
    "Menu": ("show menu", "cancel menu", "end round"),
    "Course list": ("show favorites", "show installed", "clear course"),
    "Club": ("club up", "club down", "putter"),
    "Aim": (
        "aim left",
        "aim right",
        "aim forward",
        "aim back",
        "reset aim",
        "aim point",
        "shot cam",
        "tee left",
        "tee right",
        "stop",
        "switch hand",
    ),
    "Map": (
        "zoom in",
        "zoom out",
        "expand map",
        "mini map",
        "shrink map",
        "map mode start",
        "map mode end",
        "marker place",
        "marker left",
        "marker right",
        "marker up",
        "marker down",
        "free flight mode start",
        "flight mode start",
        "free flight mode end",
        "flight mode end",
    ),
    "View": (
        "flyover",
        "heat map",
        "scorecard",
        "close",
        "green grid",
        "pin indicator",
        "range finder",
        "look left",
        "look right",
        "hide ui",
        "show ui",
        "clear tracer",
    ),
}

# The numbered grid. Its own grammar, on only while the grid is showing: the digit words pick cells.
GRID_GROUP = "grid"
# The grid's cells are spoken with the NATO alphabet: distinct words that are less often misheard than
# digits. Each cell is labelled with the first letter of its word, A to J. "golf" is a risk: it is close
# to "please start gspro", which always listens. The first word is cell 0 on the grid, and so on.
GRID_WORDS: tuple[str, ...] = (
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliett",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "yankee",
    "zulu",
)
GRID_INDEX: dict[str, int] = {word: index for index, word in enumerate(GRID_WORDS)}
GRID_PHRASES: tuple[str, ...] = (*GRID_WORDS, "hide grid", "cancel grid")

# The commands dialog's tab phrases. Their own grammar, on only while the dialog is open (see the listener).
DIALOG_GROUP = "dialog"
DIALOG_PHRASES: tuple[str, ...] = ("show current grammar", "show always on")

# Always listening, on every screen. This is the way out when the screen memory is wrong.
GLOBAL: tuple[str, ...] = (
    "stop listening",
    "start listening",
    "please start gspro",
    "start screen",
    "open commands",
    "close commands",
    "show grid",
    *SYNC_PHRASES,
)

SCREEN_RECORDS: tuple[Screen, ...] = (
    Screen(
        "home",
        "Home",
        None,
        trans=(
            Trans("practice screen", "practice", "practice screen"),
            Trans("play screen", "local_match", "play screen"),
            Trans("challenges screen", "challenges"),
            Trans("tournaments screen", "tournaments"),
            Trans("online match", "online"),
            Trans("gspro practice range now", "range", "gspro practice range now"),  # from home, skips the practice screen
            Trans("on course practice now", "on_course", "on course practice now"),
            Trans("additional ranges now", "additional", "additional ranges now"),
        ),
        groups=("Exit",),
    ),
    Screen(
        "local_match",
        "Local match",
        "home",
        trans=(Trans("play <course>", "round_settings_play", "play course"),),
        groups=("Back", "Course list"),
        note="course chooser",
    ),
    Screen(
        "practice",
        "Practice",
        "home",
        trans=(
            Trans("gspro practice range", "range", "gspro practice range"),
            Trans("on course practice", "on_course", "on course practice"),
            Trans("additional ranges", "additional", "additional ranges"),
        ),
        groups=("Back",),
    ),
    Screen("challenges", "Challenges", "home"),
    Screen("tournaments", "Tournaments", "home"),
    Screen("online", "Online match", "home"),
    Screen("range", "GSPro Range", "practice", groups=("Menu", "Range"), note="hit balls"),
    Screen(
        "on_course",
        "On course practice",
        "practice",
        trans=(Trans("play <course>", "round_settings_practice", "play course"),),
        groups=("Back", "Course list"),
        note="course chooser",
    ),
    Screen(
        "additional",
        "Additional Driving Ranges",
        "practice",
        trans=(Trans("play <range name>", "driving_range", "play course"),),
        groups=("Back", "Course list"),
        note="range chooser",
    ),
    Screen("driving_range", "Additional Range", "additional", groups=("Menu",), note="hit balls"),
    # Round settings, reached from On course practice (practice) or Local match (play).
    Screen(
        "round_settings_practice",
        "Round Settings - Practice",
        "on_course",
        trans=(
            Trans("now", "course_practice", "now"),
            # PLAY on round settings. The course name is heard by the course grammar; the literal
            # "play course" presses PLAY for the course already set up.
            Trans("play <course>", "course_practice", "play course", aliases=("play course",)),
        ),
        groups=("Back", "Tabs"),
    ),
    Screen("course_practice", "Course Practice", "round_settings_practice", groups=("Menu", "Club", "Aim", "Map", "View", "Ball")),
    Screen(
        "round_settings_play",
        "Round Settings - Play",
        "local_match",
        trans=(
            Trans("now", "play", "now"),
            Trans("play <course>", "play", "play course", aliases=("play course",)),
        ),
        groups=("Back", "Tabs"),
    ),
    Screen("play", "Course play", "round_settings_play", groups=("Menu", "Club", "Aim", "Map", "View", "Ball"), note="hit balls"),
)

RECORDS_BY_KEY = {screen.key: screen for screen in SCREEN_RECORDS}


def screen_group(key: str) -> str:
    """The speech grammar group name for a screen."""
    return f"screen:{key}"


SCREEN_GROUP_NAMES: tuple[str, ...] = tuple(screen_group(key) for key in RECORDS_BY_KEY)

# Panels are sub-screens: a dialog or panel that opens on a screen and gets its own grammar while
# it is open. Named by what it is, since more will be added (the map will be one). Opened and
# closed by the sequences in gspro_sequences.PANEL_OPENERS and PANEL_CLOSERS.
PANELS: dict[str, tuple[str, ...]] = {
    "driving_preferences_panel": (
        "open preferences",
        "close preferences",
        "change driving range distance",
        "done",
        "apply",
        "close preferences",
        "randomizer on",
        "randomizer off",
        "change max distance",
        "change min distance",
        "change shots per one",
        "change shots per three",
        "change shots per five",
        "change shots per ten",
        "change shots per fifteen",
        "slide left",
        "slide right",
        "stop",
        *DIGIT_KEYS,
    ),
}


def panel_group(key: str) -> str:
    """The speech grammar group name for a panel."""
    return f"panel:{key}"


PANEL_GROUP_NAMES: tuple[str, ...] = tuple(panel_group(key) for key in PANELS)
PANEL_NAMES: dict[str, str] = {"driving_preferences_panel": "Driving Preferences"}  # what the tree box says
PANEL_PARENTS: dict[str, str] = {"driving_preferences_panel": "range"}  # the screen the panel opens on


def screen_phrases(key: str, spoken: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The phrases a screen's own grammar holds. A transition with no sequence yet is left out,
    so it is not heard. Club names (spoken) go with the Club group. "play <...>" phrases are
    left out here; the course grammar covers course names."""
    record = RECORDS_BY_KEY[key]
    phrases: list[str] = []
    for trans in record.trans:
        if trans.sequence:
            if "<" not in trans.phrase:
                phrases.append(trans.phrase)
            phrases.extend(trans.aliases)
    for group in record.groups:
        phrases.extend(GROUPS[group])
        if group == "Club":
            phrases.extend(spoken)
    return tuple(dict.fromkeys(phrases))


def with_aliases(phrases) -> tuple[str, ...]:
    """Each primary phrase followed by its aliases, for the speech grammar."""
    return tuple(dict.fromkeys(x for phrase in phrases for x in (phrase, *aliases_of(phrase))))


def label(phrase: str) -> str:
    """A primary phrase with its aliases in brackets, for the screen table."""
    aliases = aliases_of(phrase)
    return f"{phrase}  (also: {', '.join(aliases)})" if aliases else phrase


def recognizer_setup(spoken: tuple[str, ...] = ()) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """What the speech recognizer listens to: (always-listening phrases, screen grammars by group name).
    Always listening: GLOBAL only. A command no record claims is not heard anywhere until it is assigned to a screen or panel.
    Aliases are added to every grammar that holds their primary."""
    screen_grammars = {screen_group(key): with_aliases(screen_phrases(key, spoken)) for key in RECORDS_BY_KEY}
    panel_grammars = {panel_group(key): with_aliases(phrases) for key, phrases in PANELS.items()}
    always = with_aliases(GLOBAL)  # only GLOBAL; a command listens where a screen or panel claims it
    return always, {**screen_grammars, **panel_grammars}


def grammar_name(group: str) -> str:
    """A readable name for a grammar group, for the debug list."""
    if group.startswith("screen:"):
        record = RECORDS_BY_KEY.get(group[len("screen:"):])
        return f"Screen: {record.name}" if record else group
    if group.startswith("panel:"):
        key = group[len("panel:"):]
        return f"Panel: {PANEL_NAMES.get(key, key)}"
    names = {"courses": "Course names", GRID_GROUP: "Grid", DIALOG_GROUP: "Commands dialog"}
    return names.get(group, group)


_active_groups: set[str] = set()  # the grammar groups listening right now; the listener keeps this up to date


def set_active_groups(groups) -> None:
    _active_groups.clear()
    _active_groups.update(groups)


def active_groups() -> list[str]:
    return sorted(_active_groups)


def check() -> list[str]:
    """Compare the records with gspro_tree.py and commands.py. Returns the problems; empty means they match."""
    problems: list[str] = []
    tree = {screen.key: screen for screen in TREE_SCREENS}

    for key in sorted(tree.keys() - RECORDS_BY_KEY.keys()):
        problems.append(f"{key}: in the tree but has no record")
    for key in sorted(RECORDS_BY_KEY.keys() - tree.keys()):
        problems.append(f"{key}: has a record but is not in the tree")

    known = {phrase for row in ROWS for phrase in row.phrases} | set(SYNC_PHRASES) | set(GLOBAL)
    for group, phrases in GROUPS.items():
        for phrase in phrases:
            if phrase not in known:
                problems.append(f"group {group}: '{phrase}' is not a command in commands.py")
    for phrase in GLOBAL:
        if phrase not in known:
            problems.append(f"global: '{phrase}' is not a command in commands.py")

    for key, record in RECORDS_BY_KEY.items():
        node = tree.get(key)
        if node is None:
            continue
        if record.parent != node.parent:
            problems.append(f"{key}: parent is {record.parent!r} here but {node.parent!r} in the tree")
        trans_phrases = {t.phrase for t in record.trans}
        for child in (s for s in tree.values() if s.parent == key):
            matches = [t for t in record.trans if t.goes_to == child.key]
            if not matches:
                problems.append(f"{key}: no transition to {child.key}")
            elif "<" not in child.phrase and child.phrase not in trans_phrases:
                problems.append(f"{key}: transition to {child.key} should say '{child.phrase}'")
        for trans in record.trans:
            if trans.goes_to not in tree:
                problems.append(f"{key}: transition '{trans.phrase}' goes to unknown screen {trans.goes_to}")
        allowed = set(GLOBAL) | trans_phrases
        for group in record.groups:
            allowed |= set(GROUPS.get(group, ()))
        for action in node.actions:
            if not action.phrase:
                continue
            if action.phrase == "play":  # PLAY COURSE is covered by the "play <course>" transition
                if not any(t.phrase.startswith("play") for t in record.trans):
                    problems.append(f"{key}: the course play action has no 'play <course>' transition")
            elif action.phrase not in allowed:
                problems.append(f"{key}: action '{action.phrase}' is in the tree but not in the record")
    return problems
