"""Screen records for GSPro voice commands. These drive the speech grammar.

Each screen says what it can do in one place:
  trans   the transitions out of it: what you say, the screen it lands on, and the sequence that runs it
  groups  the property groups it has (Back, Menu, Club, and so on), from GROUPS below

Speech grammar (recognizer_setup): GLOBAL phrases are always listening. Everything else is heard
only on the screen or panel that claims it. Each screen's trans and groups form its own grammar, switched on while GSPro is on
that screen. check() compares the records with gspro_tree.py and commands.py.
"""

from dataclasses import dataclass

from app.commands import DIGIT_KEYS, ROWS, aliases_of, repeat_variants
from app.gspro_tree import SCREENS as TREE_SCREENS
from app.gspro_tree import SYNC_PHRASES
from app.grammar_words import NAV, TOGGLE


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
    phrases: tuple[str, ...] = ()  # the screen's own commands that are not transitions; they are in its grammar
    note: str = ""  # a second line on the tree box, to say what the screen is for


# Property and capability groups: the phrases each group holds. A screen has a group when
# it lists the group's name in its groups.
GROUPS: dict[str, tuple[str, ...]] = {
    "Exit": ("gspro exit", "confirm exit"),  # home screen only; exit takes two steps so it is not an accident
    "Back": ("back screen",),
    "Range": ("open preferences", "close preferences", "change driving range distance"),  # GSPro Range only: the driving range panel (see PANELS); close is here too, so it is heard after the panel memory drifts
    "Tabs": ("players tab", "match tab", "holes tab"),  # round settings: the three tabs along the top
    "Course chooser": (
        "show favorites",
        "show installed",
        "clear filter",
        f"{NAV} filter",
        "download row one",
        "download row two",
        "download row three",
        "download row four",
        "download row five",
        "download row six",
        "download row seven",
        "download row eight",
        "download row nine",
        "play row one",
        "play row two",
        "play row three",
        "play row four",
        "play row five",
        "play row six",
        "play row seven",
        "play row eight",
        "play row nine",
        "play row one now",
        "play row two now",
        "play row three now",
        "play row four now",
        "play row five now",
        "play row six now",
        "play row seven now",
        "play row eight now",
        "play row nine now",
        f"{TOGGLE} favorite row one",
        f"{TOGGLE} favorite row two",
        f"{TOGGLE} favorite row three",
        f"{TOGGLE} favorite row four",
        f"{TOGGLE} favorite row five",
        f"{TOGGLE} favorite row six",
        f"{TOGGLE} favorite row seven",
        f"{TOGGLE} favorite row eight",
        f"{TOGGLE} favorite row nine",
        "show notes one",
        "show notes two",
        "show notes three",
        "show notes four",
        "show notes five",
        "show notes six",
        "show notes seven",
        "show notes eight",
        "show notes nine",
    ),
    # "sync to <screen>": on every screen (see SCREEN_WIDE_GROUPS), not while a panel is open
    "Sync": tuple(SYNC_PHRASES),
    "Aim": (
        "aim left",
        "aim right",
        "aim forward",
        "aim back",
        "stop",
    ),
    "View": (
        "fly over",
        "close",
        "range finder",
    ),
    # Hitting groups. hitting_base is for every screen where a ball is hit (course play, course practice, and
    # later the ranges). hitting_course and hitting_range hold what is common to those screens but not to
    # each other. Commands move in here once confirmed on both screens of their kind.
    # The club grammar: club up, club down, putter, and the club names the bag has (spoken; see group_phrases).
    "Club": (
        "club putter",
    ),
    "hitting_base": (
        "stop",
        "reset aim",
        f"{TOGGLE} ui",
        "open menu",
        f"{TOGGLE} heat map",
        f"{TOGGLE} green grid",
        f"{TOGGLE} pin",
        "look left",
        "look right",
        "club up",
        "club down",
        f"{TOGGLE} hand",
    ),
    # The game menu and ending a round: on any screen with hitting base, so the menu works on every hitting screen.
    # Only while the show notes panel is open (see course_chooser.panel_open). "cancel" and "close" mean
    # other things elsewhere, so they listen only here.
    "Course notes panel": ("cancel", "close", "read more", "latest scores", "play course", "play course now"),
    "Menu": (
        "show menu",
        "cancel menu",
        "end round",
    ),
    # Course play and course practice only. Ball placement is here too (the range screens lose it until the
    # ranges are revisited).
    "hitting_course": (
        "shot cam",
        "aim point",
        "shadow one",
        "shadow two",
        "shadow three",
        "shadow four",
        "shadow five",
        "tee left",
        "tee right",
        "zoom in",
        "zoom out",
        f"{TOGGLE} map",
        "mini map",
        "shrink map",
        "place marker",
        f"{TOGGLE} free flight",
        f"{TOGGLE} flight",
        "sync map small",
        "sync map large",
    ),
    "hitting_range": (),  # the practice ranges; empty until the ranges are revisited
}

# The numbered grid. Its own grammar, on only while the grid is showing: the digit words pick cells.
GRID_GROUP = "grid"
# The grid's cells are spoken with the NATO alphabet: distinct words that are less often misheard than
# digits. Each cell is labelled with the first letter of its word, A to J. "golf" is a risk: it is close
# to "click gspro", which always listens. The first word is cell 0 on the grid, and so on.
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
GRID_PHRASES: tuple[str, ...] = (*GRID_WORDS, "hide place", "cancel place", "redo", "toggle map")

# Typing by voice (app/text_entry.py). Its grammar is on only while the course filter is typing, so it is not
# one of the screen's own groups: see RUNTIME_GROUPS.
GROUPS["Filter entry"] = (
    *GRID_WORDS,  # the NATO letters
    "space",
    "underscore",
    "dash",
    "comma",
    "period",
    "parenthesis",
    "number sign",
    "plus sign",
    "backspace",
    "stop filter",
)
RUNTIME_GROUPS: tuple[str, ...] = ("Filter entry",)

# The commands dialog's tab phrases. Their own grammar, on only while the dialog is open (see the listener).
DIALOG_GROUP = "dialog"
DIALOG_PHRASES: tuple[str, ...] = ("show current grammar", "show always on")

# Always listening, on every screen. This is the way out when the screen memory is wrong.
GLOBAL: tuple[str, ...] = (
    f"{TOGGLE} listening",
    f"{TOGGLE} keyboard",
    f"{NAV} gspro",
    f"{NAV} screen",
    f"{TOGGLE} commands",
    "fullscreen",
)

SCREEN_RECORDS: tuple[Screen, ...] = (
    Screen(
        "home",
        "Home",
        None,
        trans=(
            Trans(f"{NAV} practice", "practice", f"{NAV} practice"),
            Trans(f"{NAV} play", "local_match", f"{NAV} play"),
            Trans(f"{NAV} challenges", "challenges"),
            Trans(f"{NAV} tournaments", "tournaments"),
            Trans("online match", "online"),
            Trans(f"{NAV} range now", "range", f"{NAV} range now"),  # from home, skips the practice screen
            Trans(f"{NAV} on course practice now", "on_course", f"{NAV} on course practice now"),
            Trans(f"{NAV} additional ranges now", "additional", f"{NAV} additional ranges now"),
        ),
        groups=("Exit",),
    ),
    Screen(
        "local_match",
        "Local match",
        "home",
        trans=(Trans("play <course>", "round_settings_play", "play course"),),
        groups=("Back", "Course chooser"),
        note="course chooser",
    ),
    Screen(
        "practice",
        "Practice",
        "home",
        trans=(
            Trans(f"{NAV} range", "range", f"{NAV} range"),
            Trans(f"{NAV} on course practice", "on_course", f"{NAV} on course practice"),
            Trans(f"{NAV} additional ranges", "additional", f"{NAV} additional ranges"),
        ),
        groups=("Back",),
    ),
    Screen("challenges", "Challenges", "home"),
    Screen("tournaments", "Tournaments", "home"),
    Screen("online", "Online match", "home"),
    Screen(
        "range",
        "GSPro Range",
        "practice",
        groups=("Range", "hitting_base", "Club", "Menu", "hitting_range"),
        note="hit balls",
        phrases=("clear tracer", "change wind"),
    ),
    Screen(
        "on_course",
        "On course practice",
        "practice",
        trans=(Trans("play <course>", "round_settings_practice", "play course"),),
        groups=("Back", "Course chooser"),
        note="course chooser",
    ),
    Screen(
        "additional",
        "Additional Driving Ranges",
        "practice",
        trans=(Trans("play <range name>", "driving_range", "play course"),),
        groups=("Back", "Course chooser"),
        note="range chooser",
    ),
    Screen(
        "driving_range",
        "Additional Range",
        "additional",
        groups=("hitting_base", "Club", "Menu", "hitting_range"),
        note="hit balls",
    ),
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
    Screen(
        "course_practice",
        "Course Practice",
        "round_settings_practice",
        groups=("Aim", "View", "hitting_base", "Club", "Menu", "hitting_course"),
        # Only on course practice: 8 goes to the ball, 9 and 0 move between holes. Place ball is here too.
        phrases=("place ball", "place pin", "go to ball", "previous hole", "next hole", "clear tracer", "change wind", "change hole"),
    ),
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
    Screen(
        "play",
        "Course play",
        "round_settings_play",
        groups=("Aim", "View", "hitting_base", "Club", "Menu", "hitting_course"),
        phrases=(f"{TOGGLE} scorecard",),  # course play only, not course practice
        note="hit balls",
    ),
)

RECORDS_BY_KEY = {screen.key: screen for screen in SCREEN_RECORDS}


def screen_group(key: str) -> str:
    """The speech grammar group name for a screen."""
    return f"screen:{key}"


SCREEN_GROUP_NAMES: tuple[str, ...] = tuple(screen_group(key) for key in RECORDS_BY_KEY)

# Every group in GROUPS is its own grammar, listening on each screen whose record lists it. So a group
# shows as its own grammar in the debug box and the Active commands tab, and is not copied into screens.
# A group with no phrases yet is not built.
def group_grammar(name: str) -> str:
    """The speech grammar group name for a property group."""
    return f"group:{name}"


def group_phrases(name: str, spoken: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The phrases a group's grammar holds. Club names (spoken) go with the Club group."""
    return GROUPS[name] + (tuple(spoken) if name == "Club" else ())


SCREEN_WIDE_GROUPS: tuple[str, ...] = ("Sync",)  # every screen listens to these, in addition to its own groups


def grammar_groups_for(key: str, spoken: tuple[str, ...] = ()) -> set[str]:
    """The group grammars a screen listens to: its own groups and the screen-wide ones, if they have phrases."""
    names = (*RECORDS_BY_KEY[key].groups, *SCREEN_WIDE_GROUPS)
    return {group_grammar(name) for name in names if group_phrases(name, spoken)}


GROUP_GRAMMAR_NAMES: tuple[str, ...] = tuple(
    group_grammar(name) for name in GROUPS if GROUPS[name] and name not in RUNTIME_GROUPS
)

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
    # The dialog that opens when END ROUND is pressed: it waits for confirm (cancel is not wired yet).
    "end_round_confirm": ("confirm", "cancel"),
    # The wind panel: its own grammar while it is open. "close" clicks the wind speed again.
    "wind_panel": ("change direction", "change strength", "stop", "close"),
    # The marker: while it is held, only these listen. "cancel" releases the button and leaves the panel.
    "marker_panel": ("left", "right", "up", "down", "stop", "place marker", "cancel marker", f"{TOGGLE} map"),
    # The change hole panel on course practice: a hole number clicks it, cancel closes it.
    "hole_panel": ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                   "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "cancel"),
}


def panel_group(key: str) -> str:
    """The speech grammar group name for a panel."""
    return f"panel:{key}"


PANEL_GROUP_NAMES: tuple[str, ...] = tuple(panel_group(key) for key in PANELS)
PANEL_NAMES: dict[str, str] = {
    "driving_preferences_panel": "Driving Preferences",
    "end_round_confirm": "End round confirm",
    "wind_panel": "Wind",
    "marker_panel": "Marker",
    "hole_panel": "Change hole",
}  # what the tree box says
PANEL_PARENTS: dict[str, str] = {
    "driving_preferences_panel": "range",
    "wind_panel": "range",
    "marker_panel": "play",
    "hole_panel": "course_practice",
    "end_round_confirm": "play",  # where its box sits in the tree; it opens from several screens (see PANEL_SCREEN_ONLY)
}
# Panels that close when the app is on another screen. Others stay open wherever they were opened.
PANEL_SCREEN_ONLY: dict[str, str] = {"driving_preferences_panel": "range"}


def screen_phrases(key: str) -> tuple[str, ...]:
    """The phrases a screen's own grammar holds: its transitions only. Its property groups are their own
    grammars (see grammar_groups_for). A transition with no sequence yet is left out, so it is not heard.
    "play <...>" phrases are left out here; the course grammar covers course names."""
    record = RECORDS_BY_KEY[key]
    phrases: list[str] = []
    for trans in record.trans:
        if trans.sequence:
            if "<" not in trans.phrase:
                phrases.append(trans.phrase)
            phrases.extend(trans.aliases)
    phrases.extend(record.phrases)
    return tuple(dict.fromkeys(phrases))


def with_aliases(phrases) -> tuple[str, ...]:
    """Each primary phrase followed by its aliases, for the speech grammar."""
    return tuple(dict.fromkeys(x for phrase in phrases for x in (phrase, *aliases_of(phrase), *repeat_variants(phrase))))


def label(phrase: str) -> str:
    """A primary phrase with its aliases in brackets, for the screen table."""
    aliases = aliases_of(phrase)
    return f"{phrase}  (also: {', '.join(aliases)})" if aliases else phrase


def recognizer_setup(spoken: tuple[str, ...] = ()) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """What the speech recognizer listens to: (always-listening phrases, screen grammars by group name).
    Always listening: GLOBAL only. A command no record claims is not heard anywhere until it is assigned to a screen or panel.
    Aliases are added to every grammar that holds their primary."""
    screen_grammars = {screen_group(key): with_aliases(screen_phrases(key)) for key in RECORDS_BY_KEY}
    panel_grammars = {panel_group(key): with_aliases(phrases) for key, phrases in PANELS.items()}
    group_grammars = {
        group_grammar(name): with_aliases(group_phrases(name, spoken)) for name in GROUPS if group_phrases(name, spoken)
    }
    always = with_aliases(GLOBAL)  # only GLOBAL; a command listens where a screen, panel or group claims it
    return always, {**screen_grammars, **panel_grammars, **group_grammars}


def grammar_name(group: str) -> str:
    """A readable name for a grammar group, for the debug list."""
    if group.startswith("screen:"):
        record = RECORDS_BY_KEY.get(group[len("screen:"):])
        return f"Screen: {record.name}" if record else group
    if group.startswith("panel:"):
        key = group[len("panel:"):]
        return f"Panel: {PANEL_NAMES.get(key, key)}"
    if group.startswith("group:"):
        text = group[len("group:"):].replace("_", " ")  # "hitting_base" reads "Hitting base"
        return text[:1].upper() + text[1:]
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
    for record in RECORDS_BY_KEY.values():
        for phrase in record.phrases:
            if phrase not in known:
                problems.append(f"{record.key}: '{phrase}' is not a command in commands.py")
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
        allowed = set(GLOBAL) | trans_phrases | set(record.phrases)
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
