"""GSPro screen tree: the screens, the screens each one reaches, and its actions.

Home is the root. Each screen names its parent, the screen you reach it from. Actions
stay on the screen they are listed under. Shared actions (players, settings) are
defined once and reused.

Status for an entry:
  done      a sequence for it has run successfully (saved in prefs, see gspro_sequences)
  not done  it has a sequence, but none has run successfully yet
  to do     no sequence yet; we do not have its clicks

Only the screen key and the sequence names are used by the app. Phrases are what you say.
"""

from dataclasses import dataclass

from app.prefs import get_bool

DONE = "done"
NOT_DONE = "not done"
TO_DO = "to do"


@dataclass(frozen=True)
class Block:
    """A reusable piece of screen that actions can pass through, such as a dialog.
    Chain blocks on an action in the order they appear."""

    name: str
    shot: str = ""  # reference screenshot in docs/screens/


@dataclass(frozen=True)
class Action:
    name: str
    phrase: str = ""  # voice phrase, empty until we decide on one
    sequences: tuple[str, ...] = ()  # sequence names that do it; empty until mapped
    shot: str = ""  # reference screenshot in docs/screens/
    blocks: tuple[Block, ...] = ()  # dialogs the action passes through


@dataclass(frozen=True)
class Screen:
    key: str  # also the name the sequence runner remembers it by
    name: str
    parent: str | None  # the screen this one is reached from; None for home
    phrase: str = ""  # what you say to go there
    sequences: tuple[str, ...] = ()  # sequence names that go there; empty until mapped
    actions: tuple[Action, ...] = ()
    shot: str = ""  # reference screenshot in docs/screens/


PLAYERS = Action("Players")
SETTINGS = Action("Settings")
EXIT = Action("Exit", "application exit", ("application exit",))
BACK = Action("Back", "back screen", ("back screen",))
CONFIRM = Block("Confirm dialog", shot="confirm_dialog.png")
PLAY_COURSE = Action(
    "Play a course",
    "play",
    ("play course",),
    shot="on_course_filtered.png",
)
PLAY_NOW = Action("Play now", "now", ("now",), shot="round_settings.png")
SHOW_FAVORITES = Action("Show favorites", "filter favorites", ("filter favorites",), shot="on_course_practice_favorites.png")
SHOW_INSTALLED = Action("Show installed", "filter installed", ("filter installed",))
CLEAR_COURSE = Action("Clear course search", "clear filter", ("clear filter",))
SHOW_MENU = Action("Show game menu", "show game menu", ("show game menu",), shot="training_screen.png")
EXPAND_MAP = Action("Map resize", f"toggle map", (), shot="mini_map_expanded.png")  # keystroke S, not a click
PLACE_MARKER = Action("Place marker", "place marker", ("place marker",))
SHRINK_MAP = Action("Shrink map", "shrink map", ())  # keystroke S, not a click
CHANGE_DISTANCE = Action("Change driving range distance", "change driving range distance", ("change driving range distance",), shot="driving_range_distance_dialog.png")
END_ROUND = Action(
    "Game menu: end round",
    sequences=("end round",),
    shot="game_menu.png",
    blocks=(CONFIRM,),
)

SCREENS: tuple[Screen, ...] = (
    Screen("home", "Home", None, actions=(EXIT, PLAYERS, SETTINGS), shot="home_screen.png"),
    # Children of home, in the order of the buttons: play, practice, challenges, tournaments, online match.
    Screen(
        "local_match",
        "Local match",
        "home",
        f"begin play",
        (f"begin play",),
        actions=(PLAY_COURSE, CLEAR_COURSE, SHOW_FAVORITES, SHOW_INSTALLED, BACK, PLAYERS, SETTINGS),
        shot="local_match.png",
    ),
    Screen(
        "practice",
        "Practice",
        "home",
        f"begin practice",
        (f"begin practice",),
        actions=(BACK, PLAYERS, SETTINGS),
        shot="practice_screen.png",
    ),
    Screen("challenges", "Challenges", "home", f"begin challenges"),
    Screen("tournaments", "Tournaments", "home", f"begin tournaments"),
    Screen("online", "Online match", "home", f"begin online match"),
    Screen(
        "range",
        "GSPro Range",
        "practice",
        f"begin gspro practice range",
        (f"begin gspro practice range", f"begin gspro practice range now"),
        actions=(CHANGE_DISTANCE, END_ROUND),
        shot="gspro_practice_range_screen.png",
    ),
    Screen(
        "on_course",
        "On course practice",
        "practice",
        f"begin on course practice",
        (f"begin on course practice", f"begin on course practice now"),
        actions=(PLAY_COURSE, CLEAR_COURSE, SHOW_FAVORITES, SHOW_INSTALLED, BACK, PLAYERS, SETTINGS),
        shot="on_course_practice.png",
    ),
    Screen(
        "additional",
        "Additional Driving Ranges",
        "practice",
        f"begin additional ranges",
        (f"begin additional ranges", f"begin additional ranges now"),
        actions=(BACK, PLAYERS, SETTINGS),
        shot="additional_driving_ranges_screen.png",
    ),
    Screen(
        "driving_range",
        "Additional Range",
        "additional",
        "play <range name>",
        actions=(SHOW_MENU, END_ROUND),
        shot="driving_range_screen.png",
    ),
    # Round settings is split by how it is reached: from On course practice (practice), or from
    # Local match (play). The screen is the same; the split keeps each path's sync and memory apart.
    Screen(
        "round_settings_practice",
        "Round Settings - Practice",
        "on_course",
        "play <name>",
        ("play course",),
        actions=(BACK, PLAYERS, SETTINGS),
        shot="round_settings_screen.png",
    ),
    Screen(
        "course_practice",
        "Course Practice",
        "round_settings_practice",
        "play <course>",
        ("now",),
        actions=(EXPAND_MAP, SHRINK_MAP, PLACE_MARKER, SHOW_MENU, END_ROUND),
        shot="training_screen.png",
    ),
    Screen(
        "round_settings_play",
        "Round Settings - Play",
        "local_match",
        "play <name>",
        ("play course",),
        actions=(BACK, PLAYERS, SETTINGS),
        shot="round_settings_screen.png",
    ),
    Screen(
        "play",
        "Course play",
        "round_settings_play",
        "play <course>",
        ("now",),
        actions=(EXPAND_MAP, SHRINK_MAP, PLACE_MARKER, SHOW_MENU, END_ROUND),
        shot="course_screen.png",
    ),
)

_BY_KEY = {screen.key: screen for screen in SCREENS}

# "sync to <screen>" tells the app which screen GSPro is on, when it has drifted out of sync.
# It clicks nothing. The phrase maps to a screen key.
SYNC_PHRASES: dict[str, str] = {
    "sync to home screen": "home",
    "sync to practice screen": "practice",
    "sync to gspro practice range screen": "range",
    "sync to on course practice screen": "on_course",
    "sync to additional ranges screen": "additional",
    "sync to local match screen": "local_match",
    "sync to driving range screen": "driving_range",
    "sync to round settings practice screen": "round_settings_practice",
    "sync to course practice screen": "course_practice",
    "sync to round settings play screen": "round_settings_play",
    "sync to course play screen": "play",
}


def screen(key: str | None) -> Screen | None:
    return _BY_KEY.get(key) if key else None


def children(key: str) -> list[Screen]:
    return [s for s in SCREENS if s.parent == key]


def status(sequences: tuple[str, ...]) -> str:
    if not sequences:
        return TO_DO
    if any(get_bool(f"tree.done:{name}", False) for name in sequences):
        return DONE
    return NOT_DONE
