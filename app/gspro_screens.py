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
    "Back": ("back screen",),
    "Range": ("open prefs", "change driving range distance", "slide left", "slide right"),
    "Slider": ("slide left", "slide right"),  # a slider's own words: loaded with any panel that has sliders on it
    # stop while a slider is moving (a drag or a slide). Otherwise stop belongs to the hitting group.
    "Slider stop": ("stop",),  # GSPro Range only: the driving range panel (see PANELS); close prefs is in the panel grammar
    "Tabs": ("players tab", "match tab", "holes tab"),  # round settings: the three tabs along the top
    "Course chooser": (
        "show filters",
        "clear filter",
        f"use filter",
        "download row one",
        "download row two",
        "download row three",
        "download row four",
        "download row five",
        "download row six",
        "download row seven",
        "download row eight",
        "download row nine",
        "download row one now",
        "download row two now",
        "download row three now",
        "download row four now",
        "download row five now",
        "download row six now",
        "download row seven now",
        "download row eight now",
        "download row nine now",
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
        f"toggle favorite row one",
        f"toggle favorite row two",
        f"toggle favorite row three",
        f"toggle favorite row four",
        f"toggle favorite row five",
        f"toggle favorite row six",
        f"toggle favorite row seven",
        f"toggle favorite row eight",
        f"toggle favorite row nine",
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
    ),
    "View": (
        "fly over",
        "close",
        "range finder",
    ),
    # Shown on the two screens where a ball is hit from the tee: the wind panel and the tracer.
    "Wind and tracer": ("change wind", "clear tracer"),
    # Hitting groups. hitting_base is for every screen where a ball is hit (course play, course practice, and
    # later the ranges). hitting_course and hitting_range hold what is common to those screens but not to
    # each other. Commands move in here once confirmed on both screens of their kind.
    # The club grammar: club up, club down, putter, and the club names the bag has (spoken; see group_phrases).
    "Club": (
        "club putter",
    ),
    "hitting_base": (
        "reset aim",
        f"toggle ui",
        "open menu",
        f"toggle heat map",
        f"toggle green grid",
        f"toggle pin",
        "look left",
        "look right",
        "stop",  # ends a held look left or look right, on every hitting screen (the Aim group keeps no copy)
        "club up",
        "club down",
        f"toggle hand",
    ),
    # The two dialogs that open on top of the notes panel are modal: each hears only its own close.
    "Round history panel": ("cancel",),
    "Read more panel": ("close",),
    "Menu": ("show game menu", "end round"),  # cancel is the game menu panel's own (see PANELS)
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
        f"toggle map",
        "mini map",
        "shrink map",
        "place marker",
        f"toggle free flight",
        f"toggle flight",
        "sync map small",
        "sync map large",
    ),
    "hitting_range": (),  # the practice ranges; empty until the ranges are revisited
}

# The numbered grid. Its own grammar, on only while the grid is showing: the digit words pick cells.
GRID_GROUP = "grid"
# The grid's cells are spoken with the NATO alphabet: distinct words that are less often misheard than
# digits. Each cell is labelled with the first letter of its word, A to J. "golf" is a risk: it is close
# to "start application", which always listens. The first word is cell 0 on the grid, and so on.
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

# The punctuation words the filter types (app/text_entry.py). They are listed after the letters and the digits.
PUNCTUATION_WORDS: tuple[str, ...] = ("space", "underscore", "dash", "comma", "period", "parenthesis", "number sign", "plus sign")
# Typing by voice (app/text_entry.py): the filter display's grammar. It is on only while the course filter is typing and
# it locks out the rest of the screen, so these are runtime groups (see RUNTIME_GROUPS).
GROUPS["Filter letters"] = tuple(GRID_WORDS)
GROUPS["Filter digits"] = tuple(DIGIT_KEYS)  # zero to nine
GROUPS["Filter punctuation"] = PUNCTUATION_WORDS
GROUPS["Filter backspace"] = ("backspace",)  # the display's fourth property: deletes the last character
GROUPS["Filter control"] = ("end filter",)
# The notes view when it has no cancel button (opened from additional driving ranges): its words, all but cancel.
GROUPS["Notes view without cancel"] = ("close", "read more", "latest scores", "play course", "play course now")
RUNTIME_GROUPS: tuple[str, ...] = ("Filter letters", "Filter digits", "Filter punctuation", "Filter backspace", "Filter control")

# The commands dialog's tab phrases. Their own grammar, on only while the dialog is open (see the listener).

# Always listening, on every screen. This is the way out when the screen memory is wrong.
GLOBAL: tuple[str, ...] = (
    f"toggle listening",
    f"toggle keyboard",
    f"start application",
    "toggle overlay",
    "overlay larger",
    "overlay smaller",
    "overlay red",
    "overlay blue",
    f"toggle fullscreen",
    "overlay refresh",
)

SCREEN_RECORDS: tuple[Screen, ...] = (
    Screen(
        "home",
        "Home",
        None,
        trans=(
            Trans(f"begin practice", "practice", f"begin practice"),
            Trans(f"begin play", "local_match", f"begin play"),
            Trans(f"begin challenges", "challenges", f"begin challenges"),
            Trans(f"begin tournaments", "tournaments", f"begin tournaments"),
            Trans(f"begin online match", "online", f"begin online match"),
            # Shortcuts from home: they skip the practice screen (see gspro_sequences.HOME_SHORTCUTS).
            Trans("skip to gspro practice range", "range", "skip to gspro practice range"),
            Trans("skip to on course practice", "on_course", "skip to on course practice"),
            Trans("skip to additional ranges", "additional", "skip to additional ranges"),
        ),
        phrases=("application exit",),  # home only: GSPro closes from its home screen
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
            Trans(f"begin gspro practice range", "range", f"begin gspro practice range"),
            Trans(f"begin on course practice", "on_course", f"begin on course practice"),
            Trans(f"begin additional ranges", "additional", f"begin additional ranges"),
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
        groups=("Range", "hitting_base", "Club", "hitting_range", "Wind and tracer"),
        note="hit balls",
        phrases=("show game menu", "end round"),
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
        groups=("Aim", "View", "hitting_base", "Club", "Menu", "hitting_course", "Wind and tracer"),
        # Only on course practice: 8 goes to the ball, 9 and 0 move between holes. Place ball is here too.
        phrases=("place ball", "place pin", "go to ball", "previous hole", "next hole", "change hole"),
    ),
    Screen(
        "round_settings_play",
        "Round Settings - Play",
        "local_match",
        trans=(
            Trans("play <course>", "play", "play course", aliases=("play course",)),
        ),
        groups=("Back", "Tabs"),
    ),
    Screen(
        "play",
        "Course play",
        "round_settings_play",
        groups=("Aim", "View", "hitting_base", "Club", "Menu", "hitting_course"),
        phrases=(f"toggle scorecard",),  # course play only, not course practice
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
        "open prefs",
        "close prefs",
        "type driving range distance",
        "done",
        "apply",
        "random on",
        "random off",
        "change max distance",
        "change min distance",
        "shots per one",
        "shots per three",
        "shots per five",
        "shots per ten",
        "shots per fifteen",
        *DIGIT_KEYS,
    ),
    # The dialog that opens when END ROUND is pressed: it waits for confirm (cancel is not wired yet).
    # The game menu: while it is up, only these listen. end round opens its own dialog.
    "game_menu_panel": ("cancel", "end round"),
    "end_round_confirm": ("confirm", "cancel"),
    # The wind panel: its own grammar while it is open. "close" clicks the wind speed again.
    "wind_panel": ("change direction", "change strength", "close"),
    # The marker: while it is held, only these listen. "cancel" releases the button and leaves the panel.
    "marker_panel": ("left", "right", "up", "down", "stop", "place marker", "cancel marker", f"toggle map"),
    # The change hole panel on course practice: a hole number clicks it, cancel closes it.
    "hole_panel": ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                   "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "cancel"),
}

# Views are fixed areas on a screen whose contents change with the circumstances (the course list's notes and
# filter areas). They do not disable the screen: their words add to the screen's own. Opened and closed by
# course_chooser through gspro_sequences.set_view. "cancel" and "close" mean other things elsewhere, so they
# listen only while the notes view is open. Its dialogs (read more, latest scores) are separate (see DIALOG_GROUPS).
VIEWS: dict[str, tuple[str, ...]] = {
    "notes_view": ("cancel", "close", "read more", "latest scores", "play course", "play course now"),
    "filter_view": ("filter favorites", "filter installed", "filter all", "filter trending"),
}
VIEW_NAMES: dict[str, str] = {"notes_view": "Show notes", "filter_view": "Filters"}  # what the tree box says
VIEW_PARENTS: dict[str, str] = {"notes_view": "on_course", "filter_view": "on_course"}  # where its box sits in the tree
# The screens a view can show on: the course list views open on both course screens (and the local match list for filters).
VIEW_SCREENS: dict[str, tuple[str, ...]] = {
    "notes_view": ("on_course", "additional"),
    "filter_view": ("on_course", "local_match", "additional"),
}
# Dialogs are modal: while one is up, only its own group listens. Named by the group they use.
DIALOG_GROUPS: dict[str, str] = {"read_more": "Read more panel", "latest_scores": "Round history panel"}


def panel_group(key: str) -> str:
    """The speech grammar group name for a panel."""
    return f"panel:{key}"


def view_group(key: str) -> str:
    """The speech grammar group name for a view."""
    return f"view:{key}"


# Panels with one or more sliders on them. A panel replaces its screen's grammar while it is up, so these also load the Slider group.
PANELS_WITH_SLIDERS: frozenset[str] = frozenset({"driving_preferences_panel", "wind_panel"})
PANEL_GROUP_NAMES: tuple[str, ...] = tuple(panel_group(key) for key in PANELS)
VIEW_GROUP_NAMES: tuple[str, ...] = tuple(view_group(key) for key in VIEWS)
PANEL_NAMES: dict[str, str] = {
    "driving_preferences_panel": "Driving Preferences",
    "end_round_confirm": "End round confirm",
    "wind_panel": "Wind",
    "marker_panel": "Marker",
    "hole_panel": "Change hole",
    "game_menu_panel": "Game menu",
}  # what the tree box says
PANEL_PARENTS: dict[str, str] = {
    "driving_preferences_panel": "range",
    "wind_panel": "range",
    "marker_panel": "play",
    "hole_panel": "course_practice",
    "game_menu_panel": "play",
    "end_round_confirm": "play",  # where its box sits in the tree; it opens from several screens (see PANEL_SCREEN_ONLY)
}
# Panels that close when the app is on another screen. Others stay open wherever they were opened.
PANEL_SCREEN_ONLY: dict[str, str] = {"driving_preferences_panel": "range"}


def overlay_phrases(key: str) -> tuple[str, ...]:
    """The commands a panel or view holds (both are boxes on a screen, shown in the Commands window)."""
    return PANELS.get(key, VIEWS.get(key, ()))


def overlay_name(key: str) -> str:
    return PANEL_NAMES.get(key) or VIEW_NAMES.get(key) or key


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
    view_grammars = {view_group(key): with_aliases(phrases) for key, phrases in VIEWS.items()}
    group_grammars = {
        group_grammar(name): with_aliases(group_phrases(name, spoken)) for name in GROUPS if group_phrases(name, spoken)
    }
    always = with_aliases(GLOBAL)  # only GLOBAL; a command listens where a screen, panel or group claims it
    return always, {**screen_grammars, **panel_grammars, **view_grammars, **group_grammars}


def grammar_name(group: str) -> str:
    """A readable name for a grammar group, for the debug list."""
    if group.startswith("screen:"):
        record = RECORDS_BY_KEY.get(group[len("screen:"):])
        return f"Screen: {record.name}" if record else group
    if group.startswith("panel:"):
        key = group[len("panel:"):]
        return f"Panel: {PANEL_NAMES.get(key, key)}"
    if group.startswith("view:"):
        key = group[len("view:"):]
        return f"View: {VIEW_NAMES.get(key, key)}"
    if group.startswith("group:"):
        text = group[len("group:"):].replace("_", " ")  # "hitting_base" reads "Hitting base"
        return text[:1].upper() + text[1:]
    names = {"courses": "Course names", GRID_GROUP: "Grid"}
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
        view_phrases = {p for name, ps in VIEWS.items() if key in VIEW_SCREENS.get(name, ()) for p in ps}
        allowed = set(GLOBAL) | trans_phrases | set(record.phrases) | view_phrases
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
    # The same phrase in two places a screen listens at once (its own list, a group, or GLOBAL) is a duplicate.
    for record in SCREEN_RECORDS:
        heard: dict[str, str] = {}
        sources = [("the screen", screen_phrases(record.key))]
        sources += [(name, group_phrases(name)) for name in (*record.groups, *SCREEN_WIDE_GROUPS)]
        sources.append(("GLOBAL", GLOBAL))
        for source, phrases in sources:
            for phrase in phrases:
                if phrase in heard and heard[phrase] != source:
                    problems.append(f"{record.key}: '{phrase}' is in both {heard[phrase]} and {source}")
                heard.setdefault(phrase, source)
    return problems
