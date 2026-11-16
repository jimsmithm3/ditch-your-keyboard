"""On course practice (the course chooser): narrow the list by typing part of a course name, and download a course
by its row number. The typing is in app/text_entry.py, which is reusable. The letters are drawn by
app/gspro_legend.py.
"""

import ctypes
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Callable

from app import text_entry  # no Qt here: the listener tells the window to draw the legend, on the GUI thread
from app.clicks import click
from app.connector_ui import _point, client_rect, find_window
from app.focus import _force_foreground
from app.gspro_courses import courses_matching, gspro_course_count, sync_from_gspro
from app.gspro_sequences import after_row_play, current_screen
from app.gspro_ui import GSPRO_TITLE, SEARCH_BOX
from app.grammar_words import NAV, TOGGLE

log = logging.getLogger(__name__)

# A download adds a course row when it finishes. Poll GSPro's table this often, and give up after this long.
DOWNLOAD_POLL_SECONDS = 2.0
DOWNLOAD_GIVE_UP_SECONDS = 1800.0

_done_hooks: list[Callable[[], None]] = []  # called after a finished download has been synced into our list


def on_download_done(hook: Callable[[], None]) -> None:
    """Register a call to make once a download has finished and the course list is updated (the listener
    uses this to reload the course names it hears)."""
    _done_hooks.append(hook)

# The Download button of each row, as fractions of the GSPro window. The first row is the one at the top of
# the list; the rows are one step apart. Read from the on_course_practice screenshots.
DOWNLOAD_X = 0.61
# The Play/Download button's colour is read here, at its left edge: the label in the middle is white and would
# look like neither Play nor Download. Sampled on the Play buttons at 0.585-0.595 of the width.
BUTTON_EDGE_X = 0.59
FIRST_ROW_Y = 0.2061  # 30 px above the first reading (0.22 of a 2160 px window); found by testing on the favorite hearts
ROW_STEP = 0.09

DOWNLOAD_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
DOWNLOAD_PHRASES = tuple(f"download row {word}" for word in DOWNLOAD_WORDS)
DOWNLOAD_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(DOWNLOAD_PHRASES)}
DOWNLOAD_NOW_PHRASES = tuple(f"{phrase} now" for phrase in DOWNLOAD_PHRASES)  # "now" is optional on a download; it does the same as the plain phrase
DOWNLOAD_NOW_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(DOWNLOAD_NOW_PHRASES)}
PLAY_PHRASES = tuple(f"play row {word}" for word in DOWNLOAD_WORDS)  # the same row buttons, for installed courses
PLAY_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(PLAY_PHRASES)}
PLAY_NOW_PHRASES = tuple(f"{phrase} now" for phrase in PLAY_PHRASES)  # the same, and press PLAY on round settings too
PLAY_NOW_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(PLAY_NOW_PHRASES)}
# Course notes: the icon at the left of each row's favourite heart opens the panel for that course. Positions are
# fractions of the GSPro window, read from the show notes screenshots (Read More, the panel's X, Play, round
# history, and the two modal close buttons).
NOTES_X = 0.4755
PANEL_CLOSE = (0.9605, 0.1984)
READ_MORE = (0.935, 0.634)
PANEL_PLAY = (0.833, 0.867)
ROUND_HISTORY = (0.968, 0.764)
DESCRIPTION_CLOSE = (0.740, 0.667)
HISTORY_CLOSE = (0.660, 0.257)
NOTES_PHRASES = tuple(f"show notes {word}" for word in DOWNLOAD_WORDS)
NOTES_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(NOTES_PHRASES)}

# Which part of the course panel is open: None (none), "panel" (the course panel), "description" (Read More),
# or "history" (latest scores). Cancel closes the innermost one.
_panel: str | None = None


def panel_open() -> bool:
    return _panel is not None


# Two spots on the course panel: inside where the Read More button is, and just below it (the panel's background).
READ_MORE_INSIDE = (0.906, 0.636)
READ_MORE_BELOW = (0.906, 0.655)
PANEL_LOAD_SECONDS = 0.6  # the panel takes a moment to draw before it is read
_has_read_more = True  # read when the panel opens; some courses have no description to read more of


def read_more_present() -> bool:
    return _has_read_more


def scan_panel_async() -> None:
    """Takes the help down, waits for the panel to draw, reads whether there is a Read More button, and puts the help back."""
    _pause()
    threading.Thread(target=_scan_panel_then_resume, daemon=True, name="ditch-your-keyboard-panel-scan").start()


def _scan_panel_then_resume() -> None:
    global _has_read_more
    try:
        time.sleep(PANEL_LOAD_SECONDS)
        hwnd = find_window(GSPRO_TITLE)
        if hwnd is not None:
            rect = client_rect(hwnd)
            inside = _row_colour(*_point(rect, READ_MORE_INSIDE))
            below = _row_colour(*_point(rect, READ_MORE_BELOW))
            _has_read_more = sum(abs(a - b) for a, b in zip(inside, below)) > 40
            log.info("course panel: read more %s", "shown" if _has_read_more else "not on this course")
    finally:
        _resume()


# The left end of the big blue Play button in the course panel. It is blue only while the panel is up, and it is
# the same place whatever course is shown, so the panel can be read from the screen (the course panel can't be
# seen from the app's memory once GSPro has left the course list).
PANEL_CHECK = (0.71, 0.867)


def _panel_on_screen() -> bool:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return False
    x, y = _point(client_rect(hwnd), PANEL_CHECK)
    return _is_play_button(x, y)


def check_panel_on_entry() -> None:
    """GSPro has arrived on the course list. The notes panel stays up when GSPro leaves the list, so the screen is read:
    if the panel is up, it is cancelled (the list is what the grammar and help expect), and the app's memory is set to
    match. Runs in the background, since it clicks."""
    threading.Thread(target=_close_stale_panel, daemon=True, name="ditch-your-keyboard-panel-check").start()


def _close_stale_panel() -> None:
    global _panel
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        _panel = None
        return
    for attempt in range(3):  # the X closes the panel itself; a description or history open on top may need a second cancel
        if not _panel_on_screen():
            break
        rect = client_rect(hwnd)
        if _force_foreground(hwnd):
            x, y = _point(rect, PANEL_CLOSE)
            click(x, y, "cancel: course panel left open")
        time.sleep(0.5)
    _panel = None
    log.info("course panel check: %s", "still up after 3 cancels" if _panel_on_screen() else "list is clear")
    scan_rows_async()  # arriving on the list: read the rows as they are now, since GSPro or the app may have restarted


def panel_state() -> str | None:
    """None, "panel", "description" (Read More) or "history" (latest scores): which part of the panel is up."""
    return _panel


def forget_panel() -> None:
    """GSPro left the course list, so the panel is not open any more (its state is dropped, not clicked)."""
    global _panel
    _panel = None


# The favourite heart of each row, as a fraction of the GSPro window width (the same rows as the Download buttons).
# Read from on_course_practice.png: the heart is at about 1025 of 2000 across.
FAVORITE_X = 0.5125
FAVORITE_PHRASES = tuple(f"{TOGGLE} favorite row {word}" for word in DOWNLOAD_WORDS)
FAVORITE_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(FAVORITE_PHRASES)}
PHRASES = (
    f"use filter",
    "stop filter",
    "backspace",
    *DOWNLOAD_PHRASES,
    *PLAY_PHRASES,
    *PLAY_NOW_PHRASES,
    *DOWNLOAD_NOW_PHRASES,
    *FAVORITE_PHRASES,
    *NOTES_PHRASES,
    "read more",
    "show punctuation",
    "show letters",
)
# The course rows' own commands (Play, Download, favourite, notes). Their buttons are read from the screen before the click,
# so the help boxes come down while they run (see the listener).
ROW_PHRASES = frozenset((*DOWNLOAD_PHRASES, *DOWNLOAD_NOW_PHRASES, *PLAY_PHRASES, *PLAY_NOW_PHRASES, *FAVORITE_PHRASES))  # notes reads no pixels, so the help stays up
# Heard only while the show notes panel is open, because they are also commands elsewhere ("close", "cancel").
PANEL_PHRASES = ("cancel", "close", "read more", "latest scores", "play course", "play course now")


def panel_action(phrase: str) -> str:
    """Open or close the show notes panel and its parts. The state changes here; the clicks run in the background."""
    global _panel
    after_play = False
    then_now = False
    if phrase in NOTES_NUMBER:
        number = NOTES_NUMBER[phrase]
        target = (NOTES_X, FIRST_ROW_Y + (number - 1) * ROW_STEP)
        _panel = "panel"
        scan_panel_async()
    elif phrase == "read more" and _panel == "panel":
        target = READ_MORE
        _panel = "description"
    elif phrase == "latest scores" and _panel == "panel":
        target = ROUND_HISTORY
        _panel = "history"
    elif phrase == "cancel" and _panel is not None:
        if _panel == "history":
            target, _panel = HISTORY_CLOSE, "panel"
        elif _panel == "description":
            target, _panel = DESCRIPTION_CLOSE, "panel"
        else:
            target, _panel = PANEL_CLOSE, None
    elif phrase == "close" and _panel == "description":
        target, _panel = DESCRIPTION_CLOSE, "panel"
    elif phrase in ("play course", "play course now") and _panel == "panel":
        target, _panel = PANEL_PLAY, None
        after_play = True  # round settings opens; "play course now" also presses its PLAY
        then_now = phrase == "play course now"
    else:
        return f"{phrase}: not in the course panel"
    threading.Thread(
        target=_panel_click, args=(target, phrase, after_play, then_now), daemon=True, name="ditch-your-keyboard-panel"
    ).start()
    return f"{phrase}: working"


def _panel_click(target: tuple[float, float], phrase: str, after_play: bool, then_now: bool) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("%s: GSPro not in front; not clicked", phrase)
        return
    x, y = _point(client_rect(hwnd), target)
    click(x, y, phrase)
    if after_play:
        from app.gspro_sequences import after_row_play

        log.info("%s: %s", phrase, after_row_play(then_now=then_now))


_said_course: str | None = None  # the course name as the user said it, for the round settings help box
_help_pause: Callable[[], None] | None = None  # the listener's: takes the help boxes down while the rows are read or clicked
_help_resume: Callable[[], None] | None = None  # and puts them back
ROW_STATE: dict[int, str | None] = {}  # row number -> "play" (blue button), "download" (grey), or None (no course)
SCAN_SETTLE_SECONDS = 0.15  # the help boxes take a moment to come down before the rows are read


def course_said(name: str | None) -> None:
    global _said_course
    _said_course = name


def said_course() -> str | None:
    return _said_course


def set_help_hooks(pause: Callable[[], None], resume: Callable[[], None]) -> None:
    global _help_pause, _help_resume
    _help_pause, _help_resume = pause, resume


def _pause() -> None:
    if _help_pause is not None:
        _help_pause()


def _resume() -> None:
    if _help_resume is not None:
        _help_resume()


def row_state(number: int) -> str | None:
    """"play" if row number shows an installed course, "download" if it shows one to download, None if the row is empty."""
    return ROW_STATE.get(number)


def _row_colour(x: int, y: int) -> tuple[int, int, int]:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    dc = user32.GetDC(0)
    try:
        color = gdi32.GetPixel(dc, x, y)
    finally:
        user32.ReleaseDC(0, dc)
    return color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF


def _classify(red: int, green: int, blue: int) -> str | None:
    if blue > 150 and blue - red > 60:
        return "play"  # the blue Play button
    if max(red, green, blue) - min(red, green, blue) <= 14 and 60 <= red <= 170:
        return "download"  # the grey Download button; the dark background is none of these
    return None


def scan_rows() -> None:
    """Reads each row's button from the screen. Blue is Play, grey is Download, anything else is an empty row."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return
    rect = client_rect(hwnd)
    for number in range(1, len(DOWNLOAD_WORDS) + 1):
        x, y = _point(rect, (BUTTON_EDGE_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
        ROW_STATE[number] = _classify(*_row_colour(x, y))
    log.info("rows: %s", " ".join(f"{number}={ROW_STATE[number] or 'empty'}" for number in ROW_STATE))


def scan_rows_async() -> None:
    """Takes the help boxes down, reads the rows, then puts the help back as the screen is now."""
    _pause()
    threading.Thread(target=_scan_then_resume, daemon=True, name="ditch-your-keyboard-row-scan").start()


def _scan_then_resume() -> None:
    try:
        time.sleep(SCAN_SETTLE_SECONDS)
        scan_rows()
    finally:
        _resume()


# The start of the search box, where the placeholder ("What course do you want to play?") or the typed text begins.
FILTER_TEXT_AREA = ((0.049, 0.116), (0.12, 0.136))


def filter_has_text() -> bool:
    """White means the filter has text; the grey placeholder does not. Reads a grid over the start of the box.
    The help boxes must be down first, or their labels cover the box."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return True  # cannot tell, so the clear still runs
    rect = client_rect(hwnd)
    (left, top), (right, bottom) = FILTER_TEXT_AREA
    for column in range(15):
        for row in range(5):
            x, y = _point(rect, (left + (right - left) * column / 14, top + (bottom - top) * row / 4))
            red, green, blue = _row_colour(x, y)
            if max(red, green, blue) > 200 and max(red, green, blue) - min(red, green, blue) < 40:
                return True  # white-ish: typed text
    return False


def _row_then_done(action, *args) -> None:
    """Runs a row command, then puts the help back. The rows are read again only on "refresh help"."""
    try:
        action(*args)
    finally:
        _resume()


def _row_number(phrase: str) -> int | None:
    """The row a phrase is for: "play row one now" is row 1. None for phrases that are not about one row."""
    words = phrase.split()
    word = words[-2] if words[-1] == "now" and len(words) > 1 else words[-1]
    return DOWNLOAD_WORDS.index(word) + 1 if word in DOWNLOAD_WORDS else None


def _ruled_out(phrase: str) -> str | None:
    """A row command the rows as they are cannot do: the reason to say, and no click. None when it can be done,
    or when the rows have not been read yet."""
    if not ROW_STATE:
        return None
    number = _row_number(phrase)
    if number is None:
        return None
    state = ROW_STATE.get(number)
    if phrase.startswith("play row") and state != "play":
        return f"{phrase}: that row has no installed course"
    if phrase.startswith("download row") and state != "download":
        return f"{phrase}: that row is not a download"
    if phrase.startswith("show notes") and state is None:
        return f"{phrase}: that row is empty"
    return None


def handle(phrase: str) -> str:
    """Run one chooser command. Returns the note to show. Letters arrive as NATO words while the filter is on."""
    if phrase == "show punctuation":
        text_entry.set_punctuation(True)
        return "Showing the punctuation"
    if phrase == "show letters":
        text_entry.set_punctuation(False)
        return "Showing the letters"
    refused = _ruled_out(phrase)
    if refused is not None:
        _resume()  # the listener may have taken the help down for this row; it was not clicked, so it comes back
        return refused
    if phrase in NOTES_NUMBER or phrase in PANEL_PHRASES:
        return panel_action(phrase)
    if phrase == f"use filter":
        return start_filter()
    if phrase == "stop filter":
        return stop_filter()
    if phrase == "backspace":
        return backspace()
    if phrase in DOWNLOAD_NUMBER:
        return download(DOWNLOAD_NUMBER[phrase])
    if phrase in DOWNLOAD_NOW_NUMBER:
        return download(DOWNLOAD_NOW_NUMBER[phrase])
    if phrase in PLAY_NUMBER:
        return play(PLAY_NUMBER[phrase], then_now=False)
    if phrase in PLAY_NOW_NUMBER:
        return play(PLAY_NOW_NUMBER[phrase], then_now=True)
    if phrase in FAVORITE_NUMBER:
        return favorite(FAVORITE_NUMBER[phrase])
    if text_entry.active() and text_entry.accepts(phrase):
        text_entry.type_phrase(phrase)
        return _narrowed()
    return ""


def _key(text: str) -> str:
    """Letters and digits only, lower case: spaces and punctuation do not count when matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _narrowed() -> str:
    """After each letter: when only one course still matches (name, location or designer, as GSPro's filter
    does), the filter has done its job. It stops, and that course is row one, so "play row one" or "show notes one"
    is what comes next."""
    typed = text_entry.typed()
    if not _key(typed):
        return f"Filter: {typed}"
    matches = courses_matching(typed)
    if not matches:
        return f"Filter: {typed}: no course matches"
    if len(matches) == 1:
        text_entry.stop()
        return f"Filter: {typed}: one course, {matches[0]}. Say play row one or show notes one"
    return f"Filter: {typed} ({len(matches)} courses)"


def start_filter() -> str:
    if current_screen() != "on_course":
        return f"use filter: say on course practice first"
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        return f"use filter: GSPro not in front"
    click(*_point(client_rect(hwnd), SEARCH_BOX), f"use filter: search box")
    text_entry.start()
    return "Filter on: say a letter, or backspace"


def stop_filter() -> str:
    text_entry.stop()
    return "Filter off"


def backspace() -> str:
    if not text_entry.active():
        return f"backspace: say use filter first"
    if not text_entry.backspace():
        return "backspace: nothing typed to delete"
    return f"Filter: {text_entry.typed()}"


def download(number: int) -> str:
    """Click the Download button of row number. Runs in the background, since the clicks take a moment."""
    threading.Thread(
        target=_row_then_done, args=(_download_now, number), daemon=True, name="ditch-your-keyboard-download"
    ).start()
    return f"download {number}: working"


def favorite(number: int) -> str:
    """Click the favourite heart of row number, which turns that course's favourite on or off. Runs in the background."""
    threading.Thread(
        target=_row_then_done, args=(_favorite_now, number), daemon=True, name="ditch-your-keyboard-favorite"
    ).start()
    return f"{TOGGLE} favorite {number}: working"


def _favorite_now(number: int) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info(f"{TOGGLE} favorite %d: GSPro not in front; not clicked", number)
        return
    x, y = _point(client_rect(hwnd), (FAVORITE_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    click(x, y, f"{TOGGLE} favorite {number}")


def play(number: int, then_now: bool) -> str:
    """Click the Play button of row number, for a course already installed. then_now also presses PLAY on
    round settings, so the round starts. Runs in the background."""
    course_said(None)  # a row has no course name said with it
    threading.Thread(
        target=_row_then_done, args=(_play_now, number, then_now), daemon=True, name="ditch-your-keyboard-play"
    ).start()
    return f"play {number}{' now' if then_now else ''}: working"


def _play_now(number: int, then_now: bool) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("play %d: GSPro not in front; not clicked", number)
        return
    rect = client_rect(hwnd)
    x, y = _point(rect, (DOWNLOAD_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    edge_x, edge_y = _point(rect, (BUTTON_EDGE_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    if not _is_play_button(edge_x, edge_y):
        log.info("play %d: that row shows Download (not installed); not clicked", number)
        return
    click(x, y, f"play {number}")
    log.info("play %d: %s", number, after_row_play(then_now))


def _download_now(number: int) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("download %d: GSPro not in front; not clicked", number)
        return
    rect = client_rect(hwnd)
    x, y = _point(rect, (DOWNLOAD_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    edge_x, edge_y = _point(rect, (BUTTON_EDGE_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    if _is_play_button(edge_x, edge_y):
        log.info("download %d: that row shows Play (already installed); not clicked", number)
        return
    try:
        before = gspro_course_count()
    except sqlite3.Error:
        log.exception("download %d: cannot read GSPro's course table; not watching for the finish", number)
        before = None
    click(x, y, f"download {number}")
    if before is not None:
        _watch_for_new_course(before, number)


def _watch_for_new_course(before: int, number: int) -> None:
    """Wait for GSPro's course table to gain a row, then sync the course list and tell the hooks."""
    threading.Thread(
        target=_watch_now, args=(before, number), daemon=True, name="ditch-your-keyboard-download-watch"
    ).start()


def _watch_now(before: int, number: int) -> None:
    deadline = time.monotonic() + DOWNLOAD_GIVE_UP_SECONDS
    while time.monotonic() < deadline:
        time.sleep(DOWNLOAD_POLL_SECONDS)
        try:
            count = gspro_course_count()
        except sqlite3.Error:
            continue  # GSPro may be writing the database; try again on the next poll
        if count > before:
            log.info("download %d finished: GSPro now has %d courses", number, count)
            try:
                sync_from_gspro()
            except sqlite3.Error:
                log.exception("download %d: could not sync the course list", number)
                return
            for hook in list(_done_hooks):
                hook()
            return
    log.info("download %d: no new course seen in GSPro after %d seconds", number, DOWNLOAD_GIVE_UP_SECONDS)


def _is_play_button(x: int, y: int) -> bool:
    """A Play button is blue. A Download button is grey, so a blue pixel means the course is installed."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    dc = user32.GetDC(0)
    try:
        color = gdi32.GetPixel(dc, x, y)
    finally:
        user32.ReleaseDC(0, dc)
    red, blue = color & 0xFF, (color >> 16) & 0xFF
    return blue > 150 and blue - red > 60
