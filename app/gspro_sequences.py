"""Chained GSPro clicks for voice commands, from one shared runner.

A sequence is a list of steps. Each step clicks one position in GSPro's window. A step
can also name a watch area: the runner samples that area before the click and waits for
it to change afterwards, so the next click waits for the screen to respond.

To add a command, add an entry to SEQUENCES and a matching phrase in commands.py.
Positions and watch areas are in gspro_ui.py. Every click goes through clicks.click, so
each one logs its label, point, and window in front.

Clicks never move the pointer afterwards. Moving it right after a click cancelled it.
"""

import atexit
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

from app.clicks import HOVER_SECONDS, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE, PRESS_SECONDS, _send, click
from app.prefs import get_pref, set_bool
from app.connector_ui import _point, _rect, find_window
from app.focus import _force_foreground
from app.gspro_ui import (
    BACK_BUTTON,
    CLEAR_SEARCH_CLICK,
    ADDITIONAL_CARD,
    COURSE_LIST_WATCH,
    LOCAL_CARD,
    CONFIRM_BUTTON,
    END_ROUND_BUTTON,
    EXIT_BUTTON,
    FILTER_FAVORITES,
    FILTER_INSTALLED,
    FIRST_PLAY,
    GSPRO_TITLE,
    MENU_BUTTON,
    MENU_CLOSE,
    HOME_WATCH,
    ON_COURSE_CARD,
    MAP_EXPANDED_CENTER,
    MAP_SMALL_CENTER,
    ROUND_PLAY,
    SEARCH_BOX,
    MENU_BUTTON,
    PRACTICE_CARD,
    RANGE_CARD,
    WATCH_DIALOG,
    WATCH_MENU,
    WATCH_SCREEN,
)

log = logging.getLogger(__name__)

TYPE_GAP_SECONDS = 0.02  # between typed characters in the course search
PLAY_CHANGE_SECONDS = 4.0  # how long to look for the list to change after Play
FILTER_SETTLE_SECONDS = 0.2  # after typing, before Play; the course list filters almost at once
COMMAND_WAIT_SECONDS = 30.0  # a command waits this long for a running sequence to finish, instead of being dropped
WATCH_GRID = 8
CHANGE_LEVEL = 15  # average brightness difference that counts as a changed screen
CHANGE_TIMEOUT = 15.0  # give up waiting for a change after this long
POLL_SECONDS = 0.2

_lock = threading.Lock()

# The screen we think GSPro is on, from the sequences that ran. Not read from GSPro, so it
# can be wrong after a manual change. CLOSED means GSPro is not running.
CLOSED = "closed"
SCREEN_AFTER: dict[str, str] = {
    "practice screen": "practice",
    "go to range": "range",
    "gspro practice range screen": "range",
    "gspro practice range": "range",
    "home screen": "home",
    "end round": "home",  # a shortcut back to the home screen
    "please exit golf": CLOSED,
    "on course practice": "on_course",
    "additional ranges": "additional",
    "play screen": "local_match",
    "show favorites": "on_course",
    "show installed": "on_course",
    "clear course": "on_course",  # clearing the search does not leave the screen
    "now": "play",  # PLAY on round settings starts the course
    "marker place": "play",  # a click on the map does not change the screen
}
def _startup_screen() -> str:
    """Home if GSPro is already running when the app starts, otherwise closed."""
    from app.launch import _process_running

    return "home" if _process_running("GSpro.exe") else CLOSED


_screen: str | None = _startup_screen()


def set_screen(key: str | None) -> None:
    global _screen
    _screen = key


def mark_running() -> None:
    """GSPro is running but we had it as closed (started by hand, or just launched)."""
    global _screen
    if _screen == CLOSED:
        _screen = "home"

# True after "hide ui" until Esc ("show ui"). GSPro shows no buttons while hidden, so a
# sequence shows the interface first. Set by listener.py when it sends those keys.
SHOW_UI_SECONDS = 1.0
_ui_hidden = False


_map_expanded = False  # the mini map on the course screen; S toggles it, so we track each toggle


def toggle_map() -> None:
    """Call when the S key (expand or shrink map) is sent."""
    global _map_expanded
    _map_expanded = not _map_expanded


def set_ui_hidden(hidden: bool) -> None:
    global _ui_hidden
    _ui_hidden = hidden


# Marker nudging (course screen): "marker left" etc. move the pointer a little at a time from
# the map center until "stop". "marker place" clicks the center plus the offset reached.
MARKER_STEP = 0.0015  # fraction of the GSPro window per move; tune by feel
MARKER_TICK_SECONDS = 0.06  # pause between moves
MARKER_LIMIT = 0.15  # the offset never goes further than this from the map center
MARKER_DIRECTIONS: dict[str, tuple[int, int]] = {
    "marker left": (-1, 0),
    "marker right": (1, 0),
    "marker up": (0, -1),
    "marker down": (0, 1),
}
# Voice phrases for the two course-screen modes. Map mode holds the mouse button; free flight
# mode is F5 in GSPro.
MAP_MODE_PHRASES = ("map mode start", "map mode end")
FLIGHT_START_PHRASES = ("free flight mode start", "flight mode start")
FLIGHT_END_PHRASES = ("free flight mode end", "flight mode end")

_marker_offset: tuple[float, float] = (0.0, 0.0)
_marker_direction: tuple[int, int] | None = None
_marker_thread: threading.Thread | None = None
_marker_stop_event = threading.Event()
# (time, offset) each time the marker moves, so "stop" can rewind to where it was a moment
# before the stop was heard. Pref: marker_stop_lag_seconds (Preferences page).
_marker_history: deque[tuple[float, tuple[float, float]]] = deque(maxlen=400)
MARKER_STOP_LAG_KEY = "marker_stop_lag_seconds"
MARKER_STOP_LAG_DEFAULT = 1.0
_marker_mode = False  # after "map mode start": the left button is held down until "map mode end"
_flight_mode = False  # after "free flight mode start": F5 was pressed to turn free flight on


def marker_active() -> bool:
    return _marker_thread is not None and _marker_thread.is_alive()


def marker_move(phrase: str) -> str:
    """Start the marker moving, or change its direction. It keeps moving until marker_stop."""
    global _marker_direction, _marker_thread
    if _screen != "play":
        return f"{phrase}: say play screen and now first"
    if not _marker_mode:
        return f"{phrase}: say map mode start first"  # the marker moves only while the mouse button is held
    if _lock.locked():
        return f"{phrase}: wait for the running GSPro sequence to finish"
    _marker_direction = MARKER_DIRECTIONS[phrase]
    if not marker_active():
        _marker_history.clear()
        _marker_history.append((time.monotonic(), _marker_offset))  # where a rewind starts at the earliest
        _marker_stop_event.clear()
        _marker_thread = threading.Thread(target=_marker_loop, name="gspraudio-marker", daemon=True)
        _marker_thread.start()
    return f"{phrase}: moving; say stop"


def _halt_marker() -> None:
    """Stop the marker thread without moving the pointer again."""
    global _marker_direction
    _marker_direction = None
    _marker_stop_event.set()
    if marker_active():
        _marker_thread.join(timeout=2.0)


def _cursor_pixel() -> tuple[int, int]:
    import ctypes
    from ctypes import wintypes

    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def marker_start() -> str:
    """Press and hold the left button on the mini map center, as GSPro's marker mode expects.
    GSPro then shows the distances, and they update as the marker moves while held."""
    global _marker_mode, _marker_offset
    if _screen != "play":
        return "map mode start: say play screen and now first"
    if _marker_mode:
        return "Already in map mode; say map mode end to finish"
    if _lock.locked():
        return "map mode start: wait for the running GSPro sequence to finish"
    _halt_marker()
    _marker_offset = (0.0, 0.0)
    _marker_history.clear()
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return "GSPro window not found"
    if not _force_foreground(hwnd):
        return "could not bring GSPro to the front; not started"
    _show_interface()
    x, y = _point(_rect(hwnd), _marker_point())
    _send(MOUSEEVENTF_MOVE, x, y)
    time.sleep(HOVER_SECONDS)
    _send(MOUSEEVENTF_LEFTDOWN, x, y)  # held until map mode end
    time.sleep(PRESS_SECONDS)  # let GSPro register the first placement at the center before any move
    _marker_mode = True
    log.info("map mode: button held at (%d,%d)", x, y)
    return "Map mode: button held at the center; move with marker left etc., say map mode end to finish"


def marker_end() -> str:
    """Stop any movement and let go of the mouse button, which leaves map mode."""
    if not _marker_mode:
        return "Not in map mode"
    return _release_marker()


def _release_marker() -> str:
    """Let go of the held button where the pointer is now, and leave map mode."""
    global _marker_mode
    _halt_marker()
    if not _marker_mode:
        return "Not in map mode"
    _marker_mode = False
    x, y = _cursor_pixel()
    _send(MOUSEEVENTF_LEFTUP, x, y)
    log.info("map mode ended: button released at (%d,%d)", x, y)
    return "Marker placed; map mode ended"


def _press_f5() -> bool:
    """Press F5 in GSPro. Returns False if GSPro could not be brought to the front."""
    import pydirectinput

    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        return False
    _show_interface()
    pydirectinput.press("f5")
    return True


def flight_mode_start() -> str:
    """F5 turns free flight on in GSPro."""
    global _flight_mode
    if _screen != "play":
        return "free flight mode: say play screen and now first"
    if _flight_mode:
        return "Already in free flight mode; say free flight mode end to leave"
    if not _press_f5():
        return "could not bring GSPro to the front; not started"
    _flight_mode = True
    return "Free flight mode on; say free flight mode end to leave"


def flight_mode_end() -> str:
    """F5 again turns free flight off in GSPro. Assumes F5 is the toggle."""
    global _flight_mode
    if not _flight_mode:
        return "Not in free flight mode"
    if not _press_f5():
        return "could not bring GSPro to the front; free flight mode still on"
    _flight_mode = False
    return "Free flight mode off"


def _release_on_exit() -> None:
    """If the app closes while marker mode holds the mouse button, let it go so it is not stuck down.
    Runs on a normal exit only; a forced kill (such as taskkill /F) does not run it."""
    try:
        if _marker_mode:
            log.info("app closing in marker mode: releasing the mouse button")
            _release_marker()
    except Exception:
        log.exception("could not release the mouse button on exit")


atexit.register(_release_on_exit)


def _marker_lag() -> float:
    try:
        return max(0.0, float(get_pref(MARKER_STOP_LAG_KEY, str(MARKER_STOP_LAG_DEFAULT))))
    except ValueError:
        return MARKER_STOP_LAG_DEFAULT


def _marker_point() -> tuple[float, float]:
    """The marker's spot as a fraction of the window: the map center plus the offset."""
    center = MAP_EXPANDED_CENTER if _map_expanded else MAP_SMALL_CENTER
    return (center[0] + _marker_offset[0], center[1] + _marker_offset[1])


def _offset_at(moment: float) -> tuple[float, float]:
    """The offset the marker had at a moment: the last move made at or before it."""
    chosen = None
    for when, offset in _marker_history:
        if when > moment:
            break
        chosen = offset
    if chosen is None:
        return _marker_history[0][1] if _marker_history else _marker_offset
    return chosen


def _aim_marker_now() -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return
    _send(MOUSEEVENTF_MOVE, *_point(_rect(hwnd), _marker_point()))


def marker_stop() -> str:
    global _marker_direction, _marker_offset
    if not marker_active():
        return "Marker was not moving"
    stopped_at = time.monotonic()
    _halt_marker()
    # The stop was heard a moment after it was said, so the marker had already moved on.
    # Rewind to where it was that much earlier.
    lag = _marker_lag()
    rewound = _offset_at(stopped_at - lag)
    log.info("marker stopped; rewound %.2f s from %s to %s", lag, _marker_offset, rewound)
    _marker_offset = rewound
    _aim_marker_now()
    _marker_history.clear()
    return "Marker stopped; say map mode end to finish"


def _marker_loop() -> None:
    global _marker_offset
    while not _marker_stop_event.is_set():
        direction = _marker_direction
        if direction is None or _screen != "play":
            break  # stopped, or the screen changed under us
        hwnd = find_window(GSPRO_TITLE)
        if hwnd is None:
            break
        rect = _rect(hwnd)
        # The window is wider than it is tall, so the same fraction of the width is more pixels
        # than of the height. Scale the sideways step so both directions move the same distance.
        aspect = (rect[3] - rect[1]) / max(rect[2] - rect[0], 1)
        x = min(max(_marker_offset[0] + direction[0] * MARKER_STEP * aspect, -MARKER_LIMIT), MARKER_LIMIT)
        y = min(max(_marker_offset[1] + direction[1] * MARKER_STEP, -MARKER_LIMIT), MARKER_LIMIT)
        _marker_offset = (x, y)
        _marker_history.append((time.monotonic(), _marker_offset))
        _send(MOUSEEVENTF_MOVE, *_point(rect, _marker_point()))  # a move only, no click; no log line per move
        _marker_stop_event.wait(MARKER_TICK_SECONDS)


def _show_interface() -> None:
    global _ui_hidden
    if not _ui_hidden:
        return
    import pydirectinput

    pydirectinput.press("esc")
    _ui_hidden = False
    log.info("interface was hidden; pressed Esc to show it")
    time.sleep(SHOW_UI_SECONDS)


@dataclass(frozen=True)
class Step:
    label: str
    target: tuple[float, float]
    watch: tuple[float, float, float, float] | None = None  # wait for this area to change
    repeat: int = 1  # more than 1: click until the watch area stops changing (must be the last step)
    wait: float = CHANGE_TIMEOUT  # seconds to wait for the change
    quiet: tuple[float, float, float, float] | None = None  # wait until this area holds still before clicking
    key: str | None = None  # pressed after the click
    settle: str = "long"  # pause after a quiet wait: "short" for quick screens, "long" otherwise


SEQUENCES: dict[str, tuple[Step, ...]] = {
    "practice screen": (Step("PRACTICE", PRACTICE_CARD),),
    "gspro practice range screen": (Step("PRACTICE RANGE", RANGE_CARD),),
    "go to range": (
        Step("PRACTICE", PRACTICE_CARD, WATCH_SCREEN),
        Step("PRACTICE RANGE", RANGE_CARD),
    ),
    "go back": (Step("BACK", BACK_BUTTON),),
    # Clicks BACK until a click does nothing, which means home (or as close as it can get).
    "home screen": (Step("BACK", BACK_BUTTON, HOME_WATCH, repeat=8, wait=4.0),),
    "please exit golf": (Step("EXIT", EXIT_BUTTON, quiet=HOME_WATCH),),
    "on course practice": (Step("ON COURSE PRACTICE", ON_COURSE_CARD, WATCH_SCREEN),),
    "additional ranges": (Step("ADDITIONAL RANGES", ADDITIONAL_CARD, WATCH_SCREEN),),
    "play screen": (Step("LOCAL MATCH", LOCAL_CARD, WATCH_SCREEN),),
    # Plays the course that is set up on round settings. "play course" with no name does the same.
    "now": (Step("PLAY", ROUND_PLAY),),
    "marker place": (Step("MARKER", MAP_SMALL_CENTER),),
    "clear course": (Step("CLEAR SEARCH", CLEAR_SEARCH_CLICK, key="backspace"),),
    "show favorites": (Step("FAVORITES", FILTER_FAVORITES),),
    "show installed": (Step("INSTALLED", FILTER_INSTALLED),),
    "show menu": (Step("GAME MENU", MENU_BUTTON),),
    "cancel menu": (Step("CANCEL MENU", MENU_CLOSE),),
    "end round": (
        Step("GAME MENU", MENU_BUTTON, WATCH_MENU),
        Step("END ROUND", END_ROUND_BUTTON, WATCH_DIALOG),
        Step("CONFIRM", CONFIRM_BUTTON, WATCH_DIALOG),
    ),
}
# Second phrases for the same sequence: the screen word can be left off a multi-word name.
SEQUENCES["gspro practice range"] = SEQUENCES["gspro practice range screen"]
SEQUENCES["back screen"] = SEQUENCES["go back"]


def _watch_grid(rect: tuple[int, int, int, int], box) -> list[float]:
    """Brightness at a grid of points inside box. Compared before and after a click."""
    import ctypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    left, top, right, bottom = rect
    x0 = left + (right - left) * box[0]
    x1 = left + (right - left) * box[2]
    y0 = top + (bottom - top) * box[1]
    y1 = top + (bottom - top) * box[3]
    values: list[float] = []
    dc = user32.GetDC(0)
    try:
        for i in range(WATCH_GRID):
            for j in range(WATCH_GRID):
                x = round(x0 + (x1 - x0) * i / (WATCH_GRID - 1))
                y = round(y0 + (y1 - y0) * j / (WATCH_GRID - 1))
                color = gdi32.GetPixel(dc, x, y)
                red, green, blue = color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF
                values.append(0.299 * red + 0.587 * green + 0.114 * blue)
    finally:
        user32.ReleaseDC(0, dc)
    return values


QUIET_SECONDS = 0.5  # sample gap when waiting for a screen to hold still
QUIET_TIMEOUT = 10.0  # give up waiting for quiet after this long and click anyway
# Two pauses after a screen looks settled. Set on the Preferences page; read at each use.
# Short: screens that load quickly, such as round settings. Long: screens that take longer.
SETTLE_KEY = "gspro_settle_seconds"
SETTLE_DEFAULT = 1.0
SHORT_SETTLE_KEY = "gspro_settle_short_seconds"
SHORT_SETTLE_DEFAULT = 0.3
# Screens with a course search list. "play <name>" works on these, and the course names listen only here.
COURSE_LIST_SCREENS = ("on_course", "additional", "local_match")


def _settle_floor(short: bool = False) -> float:
    from app.prefs import get_pref

    key, default = (SHORT_SETTLE_KEY, SHORT_SETTLE_DEFAULT) if short else (SETTLE_KEY, SETTLE_DEFAULT)
    try:
        return max(0.0, float(get_pref(key, str(default))))
    except ValueError:
        return default


def _wait_until_still(hwnd: int, box) -> float | None:
    """Seconds until the watched area holds still, or None if it keeps moving."""
    from app.progress import set_working

    set_working("waiting for the screen to settle")
    started = time.monotonic()
    before = _watch_grid(_rect(hwnd), box)
    while time.monotonic() - started < QUIET_TIMEOUT:
        time.sleep(QUIET_SECONDS)
        now = _watch_grid(_rect(hwnd), box)
        if sum(abs(a - b) for a, b in zip(before, now)) / len(before) < CHANGE_LEVEL:
            return time.monotonic() - started
        before = now
    return None


def _wait_for_change(hwnd: int, box, before: list[float], timeout: float = CHANGE_TIMEOUT) -> float | None:
    """Seconds until the watched area changes, or None if it does not change in time."""
    from app.progress import set_working

    set_working("waiting for the screen to change")
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        time.sleep(POLL_SECONDS)
        now = _watch_grid(_rect(hwnd), box)
        difference = sum(abs(a - b) for a, b in zip(before, now)) / len(before)
        if difference > CHANGE_LEVEL:
            return time.monotonic() - started
    return None


def _click_until_still(hwnd: int, name: str, step: Step) -> str:
    """Click a step until its watch area stops changing. That means no screen behind it: home."""
    for count in range(1, step.repeat + 1):
        if not _force_foreground(hwnd):
            return f"{name}: lost GSPro focus; stopped"
        rect = _rect(hwnd)
        before = _watch_grid(rect, step.watch)
        click(*_point(rect, step.target), f"{name} {step.label} click {count}")
        if _wait_for_change(hwnd, step.watch, before, step.wait) is None:
            backs = count - 1  # the last click did nothing, so it was not a real BACK
            if backs == 0:
                # Nothing to go back from: this is home, or a screen with no BACK in the upper left.
                log.info("%s: first click did nothing; home, or no BACK in the upper left here", name)
                return f"{name}: nothing to go back from here (home, or no BACK in the upper left)"
            log.info("%s: no change after click %d; at home after %d BACK click(s)", name, count, backs)
            return f"{name}: at home after {backs} BACK click(s)"
        log.info("%s: %s click %d changed the screen", name, step.label, count)
    log.warning("%s: still changing after %d clicks; stopped", name, step.repeat)
    return f"{name}: still changing after {step.repeat} BACK clicks; stopped"


def run_course_in_background(
    text: str, on_done: Callable[[str], None] | None = None, then_now: bool = False
) -> str:
    """Play a course from the on course practice list: type the name in the search box,
    then press Play on the first row. text is what was said after "play". then_now also
    presses PLAY on round settings, so the round starts."""
    if not text and _screen != "round_settings":
        return "Say the course name after play"
    # Take the lock here, before the thread starts. A command said right after this one then
    # waits for the course to finish, instead of slipping in ahead of it.
    if not _lock.acquire(timeout=COMMAND_WAIT_SECONDS):
        return "Already running a GSPro sequence"

    def run() -> None:
        try:
            note = _play_course(text)
            if then_now and note.endswith(": done"):
                later = _run("now")
                _remember_screen("now", later)
                note = f"{note}; {later}"
        finally:
            from app.progress import clear as clear_working

            clear_working()
            _lock.release()  # a lock may be released by the thread that did not take it
        log.info("%s", note)
        if on_done is not None:
            on_done(note)

    threading.Thread(target=run, name="gspraudio-play-course", daemon=True).start()
    return f"Playing {text}"


def _clear_course_filter(hwnd: int) -> None:
    """Empty the course search so the full list shows. GSPro keeps the last search when you
    come back to the screen. A click on the first letter selects all the text, and one
    Backspace clears it."""
    import pydirectinput

    from app.progress import set_working

    set_working("clearing the course search")
    click(*_point(_rect(hwnd), CLEAR_SEARCH_CLICK), "clear course search: first letter")
    pydirectinput.press("backspace")


def _play_course(text: str) -> str:
    global _screen
    if _screen == CLOSED:
        return "GSPro is not running. Say please play golf."
    if _screen == "round_settings":
        # The course is already set up here, so the name is not needed: press PLAY.
        hwnd = find_window(GSPRO_TITLE)
        if hwnd is None or not _force_foreground(hwnd):
            return "could not bring GSPro to the front; not clicked"
        _show_interface()
        click(*_point(_rect(hwnd), ROUND_PLAY), "play course: round settings PLAY")
        _screen = "play"
        return "play course: done"
    if _screen not in COURSE_LIST_SCREENS:
        return "play course: say on course practice or additional ranges first"
    source = _screen  # which list we are on decides the screen that opens after Play
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return "GSPro window not found"
    if not _force_foreground(hwnd):
        return "could not bring GSPro to the front; not clicked"
    _show_interface()

    import pydirectinput

    _clear_course_filter(hwnd)
    click(*_point(_rect(hwnd), SEARCH_BOX), f"play course {text}: search box")
    typed_at = time.monotonic()
    for character in text:
        if character == " ":
            pydirectinput.press("space", _pause=False)
        elif character.isalnum():
            pydirectinput.press(character, _pause=False)  # no built-in pause; the gap below sets the speed
        time.sleep(TYPE_GAP_SECONDS)
    log.info("play course %s: typed in %.1f s", text, time.monotonic() - typed_at)
    time.sleep(FILTER_SETTLE_SECONDS)  # the list filters almost at once; no long wait needed
    before_click = _watch_grid(_rect(hwnd), COURSE_LIST_WATCH)
    click(*_point(_rect(hwnd), FIRST_PLAY), f"play course {text}: first row Play")
    # Round settings may not change the list area's brightness much, so this wait is short.
    if _wait_for_change(hwnd, COURSE_LIST_WATCH, before_click, timeout=PLAY_CHANGE_SECONDS) is None:
        log.info("play course %s: list area did not change after Play; going on", text)
    if _wait_until_still(hwnd, HOME_WATCH) is None:
        log.warning("play course %s: round settings kept moving", text)
    time.sleep(_settle_floor(short=True))  # round settings load quickly
    # Play on a course opens round settings ("now" presses its PLAY). Play on an additional
    # range opens the driving range screen instead, which has no PLAY to press.
    _screen = "driving_range" if source == "additional" else "round_settings"
    set_bool("tree.done:play course", True)
    return f"play course {text}: done"


def run_in_background(name: str, on_done: Callable[[str], None] | None = None) -> str:
    """Start a sequence on a background thread. Returns a note for the status bar at once."""

    def run() -> None:
        note = run_sequence(name)
        if on_done is not None:
            on_done(note)

    threading.Thread(target=run, name=f"gspraudio-{name}", daemon=True).start()
    return f"Running {name}"


def run_sequence(name: str) -> str:
    if not _lock.acquire(timeout=COMMAND_WAIT_SECONDS):
        return "Already running a GSPro sequence"
    from app.progress import clear as clear_working, set_working

    set_working(f"{name}: starting")
    try:
        note = _run(name)
        _remember_screen(name, note)
        if note.endswith(": done") or "at home" in note:
            set_bool(f"tree.done:{name}", True)  # ran successfully: shows as done on Overview
        if name == "please exit golf" and (note.endswith(": done") or note.startswith("GSPro is not running")):
            from app.launch import stop_connector

            log.info("exit golf: %s", stop_connector())  # the connector goes with GSPro
        return note
    finally:
        clear_working()
        _lock.release()


def sync_screen(key: str) -> str:
    """Set the remembered screen without clicking anything."""
    from app.gspro_tree import screen

    set_screen(key)
    found = screen(key)
    return f"Synced to {found.name if found else key}"


def current_screen() -> str | None:
    """The screen key we last knew GSPro to be on, or None when unknown."""
    return _screen


def _remember_screen(name: str, note: str) -> None:
    global _screen, _marker_mode
    if note.startswith(("Already running", "GSPro window not found", "GSPro is not running")):
        return  # nothing was clicked, so the screen is unchanged
    if name == "home screen" and "at home" in note:
        _screen = "home"
    elif name in ("go back", "back screen") and note.endswith(": done") and _screen:
        # BACK goes to the screen this one is reached from, as the tree says.
        from app.gspro_tree import screen

        found = screen(_screen)
        _screen = found.parent if found is not None and found.parent else _screen
    elif note.endswith(": done") and name in SCREEN_AFTER:
        _screen = SCREEN_AFTER[name]
    else:
        _screen = None  # clicked something we do not track; the screen is unknown
    if _screen != "play" and _marker_mode:
        _release_marker()  # never leave the mouse button held once the play screen is gone


def _run(name: str) -> str:
    global _screen
    if _screen == CLOSED:
        return "GSPro is not running. Say please play golf."
    if name in ("show favorites", "show installed", "clear course") and _screen not in COURSE_LIST_SCREENS:
        return f"{name}: say on course practice first"
    if name == "now" and _screen != "round_settings":
        return "now: say play course and the course name first"
    if name == "marker place" and _screen != "play":
        return "marker place: say play screen and now first"
    if name == "marker place" and _marker_mode:
        return "marker place: map mode is on; say map mode end to finish"
    if name == "please exit golf" and _screen != "home":
        # EXIT is only on the home screen, so get there first with the same routine as "home screen".
        home = _run("home screen")
        if not (home.endswith(": done") or "at home" in home or "nothing to go back" in home):
            return f"{name}: could not get to the home screen first ({home})"
        _screen = "home"
    # Home is not skipped even when the memory says home: a screen we did not track may
    # have a BACK button, and on a real home screen the first BACK click does nothing.
    if name == "home screen" and _screen in ("range", "play", "driving_range"):
        name = "end round"  # from the range or a course, going home is ending the round
    steps = SEQUENCES[name]
    if name == "marker place":
        marker_stop()  # a moving marker stops before it is placed
        # The map is small or expanded; its center is in a different place for each. The
        # offset from "marker left" and friends moves the click away from that center.
        center = MAP_EXPANDED_CENTER if _map_expanded else MAP_SMALL_CENTER
        steps = (Step("MARKER", (center[0] + _marker_offset[0], center[1] + _marker_offset[1])),)
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return "GSPro window not found"
    if not _force_foreground(hwnd):
        log.warning("%s: could not bring GSPro to the front", name)
        return "could not bring GSPro to the front; not clicked"
    _show_interface()

    log.info("%s: start, %d step(s), window rect %s", name, len(steps), _rect(hwnd))
    started = time.monotonic()
    for number, step in enumerate(steps, start=1):
        if step.repeat > 1:
            note = _click_until_still(hwnd, name, step)
            log.info("%s: done in %.1f s", name, time.monotonic() - started)
            return note
        if step.quiet is not None:
            if _wait_until_still(hwnd, step.quiet) is None:
                log.warning("%s: %s area kept moving for %.0f s; clicking anyway", name, step.label, QUIET_TIMEOUT)
            time.sleep(_settle_floor(short=step.settle == "short"))  # a pause after it looks still, so the screen finishes loading
        rect = _rect(hwnd)
        before = _watch_grid(rect, step.watch) if step.watch is not None else None
        click(*_point(rect, step.target), f"{name} step {number} {step.label}")
        if step.key is not None:
            import pydirectinput

            pydirectinput.press(step.key)  # a key after the click, such as Backspace after selecting text
        if step.watch is not None:
            waited = _wait_for_change(hwnd, step.watch, before, step.wait)
            if waited is None:
                log.warning("%s: %s did not change the screen in %.0f s", name, step.label, step.wait)
                return f"{name}: {step.label} did not change the screen; stopped"
            log.info("%s: screen changed %.1f s after %s", name, waited, step.label)
        if number < len(steps) and not _force_foreground(hwnd):
            log.warning("%s: lost GSPro focus after %s", name, step.label)
            return f"{name}: lost GSPro focus after {step.label}; stopped"
    if name in ("on course practice", "play screen"):
        # The list takes a moment to fill. Then clear the old search so the full list shows.
        # Local match keeps its search too, so it gets the same clear.
        if _wait_until_still(hwnd, COURSE_LIST_WATCH) is None:
            log.warning("%s: list kept moving; clearing the filter anyway", name)
        time.sleep(_settle_floor(short=True))  # the course list is quick, so the filter clear can run sooner
        _clear_course_filter(hwnd)
    log.info("%s: done in %.1f s", name, time.monotonic() - started)
    return f"{name}: done"
