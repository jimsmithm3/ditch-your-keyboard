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
    f"{NAV} filter",
    "stop filter",
    "backspace",
    *DOWNLOAD_PHRASES,
    *PLAY_PHRASES,
    *PLAY_NOW_PHRASES,
    *FAVORITE_PHRASES,
    *NOTES_PHRASES,
    "read more",
)
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


def handle(phrase: str) -> str:
    """Run one chooser command. Returns the note to show. Letters arrive as NATO words while the filter is on."""
    if phrase in NOTES_NUMBER or phrase in PANEL_PHRASES:
        return panel_action(phrase)
    if phrase == f"{NAV} filter":
        return start_filter()
    if phrase == "stop filter":
        return stop_filter()
    if phrase == "backspace":
        return backspace()
    if phrase in DOWNLOAD_NUMBER:
        return download(DOWNLOAD_NUMBER[phrase])
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
        return f"{NAV} filter: say on course practice first"
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        return f"{NAV} filter: GSPro not in front"
    click(*_point(client_rect(hwnd), SEARCH_BOX), f"{NAV} filter: search box")
    text_entry.start()
    return "Filter on: say a letter, or backspace"


def stop_filter() -> str:
    text_entry.stop()
    return "Filter off"


def backspace() -> str:
    if not text_entry.active():
        return f"backspace: say {NAV} filter first"
    if not text_entry.backspace():
        return "backspace: nothing typed to delete"
    return f"Filter: {text_entry.typed()}"


def download(number: int) -> str:
    """Click the Download button of row number. Runs in the background, since the clicks take a moment."""
    threading.Thread(target=_download_now, args=(number,), daemon=True, name="ditch-your-keyboard-download").start()
    return f"download {number}: working"


def favorite(number: int) -> str:
    """Click the favourite heart of row number, which turns that course's favourite on or off. Runs in the background."""
    threading.Thread(target=_favorite_now, args=(number,), daemon=True, name="ditch-your-keyboard-favorite").start()
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
    threading.Thread(target=_play_now, args=(number, then_now), daemon=True, name="ditch-your-keyboard-play").start()
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
