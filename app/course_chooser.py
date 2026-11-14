"""On course practice (the course chooser): narrow the list by typing part of a course name, and download a course
by its row number. The typing is in app/text_entry.py, which is reusable. The letters are drawn by
app/gspro_legend.py.
"""

import ctypes
import logging
import sqlite3
import threading
import time
from collections.abc import Callable

from app import text_entry  # no Qt here: the listener tells the window to draw the legend, on the GUI thread
from app.clicks import click
from app.connector_ui import _point, client_rect, find_window
from app.focus import _force_foreground
from app.gspro_courses import gspro_course_count, sync_from_gspro
from app.gspro_sequences import after_row_play, current_screen
from app.gspro_ui import GSPRO_TITLE, SEARCH_BOX

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
FIRST_ROW_Y = 0.22
ROW_STEP = 0.09

DOWNLOAD_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
DOWNLOAD_PHRASES = tuple(f"download {word}" for word in DOWNLOAD_WORDS)
DOWNLOAD_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(DOWNLOAD_PHRASES)}
PLAY_PHRASES = tuple(f"play {word}" for word in DOWNLOAD_WORDS)  # the same row buttons, for installed courses
PLAY_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(PLAY_PHRASES)}
PLAY_NOW_PHRASES = tuple(f"{phrase} now" for phrase in PLAY_PHRASES)  # the same, and press PLAY on round settings too
PLAY_NOW_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(PLAY_NOW_PHRASES)}
PHRASES = ("start filter", "stop filter", "backspace", *DOWNLOAD_PHRASES, *PLAY_PHRASES, *PLAY_NOW_PHRASES)


def handle(phrase: str) -> str:
    """Run one chooser command. Returns the note to show. Letters arrive as NATO words while the filter is on."""
    if phrase == "start filter":
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
    if text_entry.active() and text_entry.accepts(phrase):
        text_entry.type_phrase(phrase)
        return f"Filter: {text_entry.typed()}"
    return ""


def start_filter() -> str:
    if current_screen() != "on_course":
        return "start filter: say on course practice first"
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        return "start filter: GSPro not in front"
    click(*_point(client_rect(hwnd), SEARCH_BOX), "start filter: search box")
    text_entry.start()
    return "Filter on: say a letter, or backspace"


def stop_filter() -> str:
    text_entry.stop()
    return "Filter off"


def backspace() -> str:
    if not text_entry.active():
        return "backspace: say start filter first"
    if not text_entry.backspace():
        return "backspace: nothing typed to delete"
    return f"Filter: {text_entry.typed()}"


def download(number: int) -> str:
    """Click the Download button of row number. Runs in the background, since the clicks take a moment."""
    threading.Thread(target=_download_now, args=(number,), daemon=True, name="gspraudio-download").start()
    return f"download {number}: working"


def play(number: int, then_now: bool) -> str:
    """Click the Play button of row number, for a course already installed. then_now also presses PLAY on
    round settings, so the round starts. Runs in the background."""
    threading.Thread(target=_play_now, args=(number, then_now), daemon=True, name="gspraudio-play").start()
    return f"play {number}{' now' if then_now else ''}: working"


def _play_now(number: int, then_now: bool) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("play %d: GSPro not in front; not clicked", number)
        return
    x, y = _point(client_rect(hwnd), (DOWNLOAD_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    if not _is_play_button(x, y):
        log.info("play %d: that row shows Download (not installed); not clicked", number)
        return
    click(x, y, f"play {number}")
    log.info("play %d: %s", number, after_row_play(then_now))


def _download_now(number: int) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("download %d: GSPro not in front; not clicked", number)
        return
    x, y = _point(client_rect(hwnd), (DOWNLOAD_X, FIRST_ROW_Y + (number - 1) * ROW_STEP))
    if _is_play_button(x, y):
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
        target=_watch_now, args=(before, number), daemon=True, name="gspraudio-download-watch"
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
