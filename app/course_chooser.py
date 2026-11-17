"""On course practice (the course chooser): narrow the list by typing part of a course name, and download a course
by its row number. The typing is in app/text_entry.py, which is reusable. The letters are drawn by
app/gspro_legend.py.
"""

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
from app.commands import DIGIT_KEYS
from app.gspro_pixels import classify_button, is_play_button, pixel_colour
from app.gspro_sequences import FILTER_VIEW, NOTES_VIEW, after_row_play, current_screen, current_view, set_view
from app.gspro_table import Column, Table
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

DIGITS = tuple(DIGIT_KEYS)  # zero to nine, in order: a digit word's index is its digit
ROW_WORDS = DIGITS[1:]  # the course list's rows are one to nine; row one is "one"
# The course list is a table (app/gspro_table.py): nine rows, one step apart, from the top of the list. Positions are
# fractions of the GSPro window, read from the on_course_practice screenshots.
COURSE_LIST = Table(
    name="course list",
    digits=DIGITS,
    rows=ROW_WORDS,
    first_row_y=0.2061,  # 30 px above the first reading (0.22 of a 2160 px window); found by testing on the favorite hearts
    row_step=0.09,
    # The Play/Download button's colour is read at its left edge: the label in the middle is white and would look
    # like neither Play nor Download. Sampled on the Play buttons at 0.585-0.595 of the width.
    edge_x=0.59,
    columns={
        # The Download or Play button. The overlay box is measured on the 16:56 screenshot (x 0.580 to 0.645).
        "button": Column(click_x=0.61, box_x=0.613, box_width=0.066),
        # The favourite heart, and the notes icon (about 44 px of the 2000 px window).
        "favorite": Column(click_x=0.5125, box_x=0.5125, box_width=0.022),
        "notes": Column(click_x=0.4755, box_x=0.4755, box_width=0.022),
    },
    row_box_dy=0.003,  # the row boxes sat about 3 px above the buttons and the notes icons
    row_half_height=0.02,
)
DOWNLOAD_PHRASES = tuple(f"download row {word}" for word in ROW_WORDS)
DOWNLOAD_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(DOWNLOAD_PHRASES)}
DOWNLOAD_NOW_PHRASES = tuple(f"{phrase} now" for phrase in DOWNLOAD_PHRASES)  # "now" is optional on a download; it does the same as the plain phrase
DOWNLOAD_NOW_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(DOWNLOAD_NOW_PHRASES)}
PLAY_PHRASES = tuple(f"play row {word}" for word in ROW_WORDS)  # the same row buttons, for installed courses
PLAY_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(PLAY_PHRASES)}
PLAY_NOW_PHRASES = tuple(f"{phrase} now" for phrase in PLAY_PHRASES)  # the same, and press PLAY on round settings too
PLAY_NOW_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(PLAY_NOW_PHRASES)}
# Course notes: the icon at the left of each row's favourite heart opens the panel for that course. Positions are
# fractions of the GSPro window, read from the show notes screenshots (Read More, the panel's X, Play, round
# history, and the two modal close buttons).
# The FILTERS button at the upper right of the list. It only shows once a row has been clicked (not a button);
# the notes view has none, so "show filters" is for when it is up.
FILTERS_BUTTON = (0.9505, 0.1263)
PANEL_CLOSE = (0.9605, 0.1984)
READ_MORE = (0.935, 0.634)
PANEL_PLAY = (0.833, 0.867)
ROUND_HISTORY = (0.968, 0.764)
DESCRIPTION_CLOSE = (0.740, 0.667)
HISTORY_CLOSE = (0.660, 0.257)
NOTES_PHRASES = tuple(f"show notes {word}" for word in ROW_WORDS)
NOTES_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(NOTES_PHRASES)}

# The notes view's details (the course panel with its Play, Read More and Latest Scores) are open or not. A dialog
# (Read More, or Latest Scores) is on top of them while it is up; it is modal, so only its own close listens.
# Kept apart: the view is in gspro_sequences.set_view, the dialog is only read here (dialog_state).
_notes_open: bool = False
_dialog: str | None = None  # None, "read_more" or "latest_scores"; cancel closes the innermost one
_notes_from: str | None = None  # the screen the notes view was opened on; only on course practice does it have a cancel button


def notes_view_open() -> bool:
    return _notes_open


def notes_view_has_cancel() -> bool:
    """On course practice the notes view has a cancel button (its X). On additional driving ranges it has none."""
    return _notes_from == "on_course"


def dialog_state() -> str | None:
    """None, "read_more" (Read More) or "latest_scores" (latest scores): which dialog is up on the notes view."""
    return _dialog


# Two spots on the course panel: inside where the Read More button is, and just below it (the panel's background).
READ_MORE_INSIDE = (0.906, 0.636)
READ_MORE_BELOW = (0.906, 0.655)
NOTES_VIEW_LOAD_SECONDS = 0.6  # the notes view takes a moment to draw before it is read
_has_read_more = True  # read when the panel opens; some courses have no description to read more of


def read_more_present() -> bool:
    return _has_read_more


def scan_notes_view_async() -> None:
    """Takes the help down, waits for the notes view to draw, reads whether there is a Read More button, and puts the overlay back."""
    _pause()
    threading.Thread(target=_scan_notes_view_then_resume, daemon=True, name="ditch-your-keyboard-notes-scan").start()


def _scan_notes_view_then_resume() -> None:
    global _has_read_more
    try:
        time.sleep(NOTES_VIEW_LOAD_SECONDS)
        hwnd = find_window(GSPRO_TITLE)
        if hwnd is not None:
            rect = client_rect(hwnd)
            inside = pixel_colour(*_point(rect, READ_MORE_INSIDE))
            below = pixel_colour(*_point(rect, READ_MORE_BELOW))
            _has_read_more = sum(abs(a - b) for a, b in zip(inside, below)) > 40
            log.info("notes view: read more %s", "shown" if _has_read_more else "not on this course")
    finally:
        _resume()


# The left end of the big blue Play button in the course panel. It is blue only while the panel is up, and it is
# the same place whatever course is shown, so the panel can be read from the screen (the course panel can't be
# seen from the app's memory once GSPro has left the course list).
NOTES_VIEW_CHECK = (0.71, 0.867)


def _notes_view_on_screen() -> bool:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return False
    x, y = _point(client_rect(hwnd), NOTES_VIEW_CHECK)
    return is_play_button(x, y)


def check_notes_view_on_entry() -> None:
    """GSPro has arrived on the course list. The notes view's details stay up when GSPro leaves the list, so the screen is read:
    if they are up, they are cancelled (the list is what the grammar and help expect), and the app's memory is set to
    match. Runs in the background, since it clicks."""
    threading.Thread(target=_close_stale_notes_view, daemon=True, name="ditch-your-keyboard-notes-check").start()


def _close_stale_notes_view() -> None:
    global _notes_open, _dialog
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        _notes_open, _dialog = False, None
        _sync_view()
        return
    for attempt in range(3):  # the X closes the details itself; a dialog open on top may need a second cancel
        if not _notes_view_on_screen():
            break
        rect = client_rect(hwnd)
        if _force_foreground(hwnd):
            x, y = _point(rect, PANEL_CLOSE)
            click(x, y, "cancel: notes view left open")
        time.sleep(0.5)
    _notes_open, _dialog = False, None
    _sync_view()
    log.info("notes view check: %s", "still up after 3 cancels" if _notes_view_on_screen() else "list is clear")
    scan_rows_async()  # arriving on the list: read the rows as they are now, since GSPro or the app may have restarted


def forget_notes_view() -> None:
    """GSPro left the course list, so the notes view is not open any more (its state is dropped, not clicked)."""
    global _notes_open, _dialog
    _notes_open, _dialog = False, None
    _sync_view()


# The favourite heart of each row, as a fraction of the GSPro window width (the same rows as the Download buttons).
# Read from on_course_practice.png: the heart is at about 1025 of 2000 across.
FAVORITE_PHRASES = tuple(f"toggle favorite row {word}" for word in ROW_WORDS)
FAVORITE_NUMBER: dict[str, int] = {phrase: index + 1 for index, phrase in enumerate(FAVORITE_PHRASES)}
PHRASES = (
    f"use filter",
    "end filter",
    "show filters",
    "backspace",
    *DOWNLOAD_PHRASES,
    *PLAY_PHRASES,
    *PLAY_NOW_PHRASES,
    *DOWNLOAD_NOW_PHRASES,
    *FAVORITE_PHRASES,
    *NOTES_PHRASES,
    "read more",
)
# The course rows' own commands (Play, Download, favourite, notes). Their buttons are read from the screen before the click,
# so the overlay boxes come down while they run (see the listener).
ROW_PHRASES = frozenset((*DOWNLOAD_PHRASES, *DOWNLOAD_NOW_PHRASES, *PLAY_PHRASES, *PLAY_NOW_PHRASES, *FAVORITE_PHRASES))  # notes reads no pixels, so the help stays up
# Heard only while the show notes panel is open, because they are also commands elsewhere ("close", "cancel").
NOTES_VIEW_PHRASES = ("cancel", "close", "read more", "latest scores", "play course", "play course now")


def notes_view_action(phrase: str) -> str:
    """Open or close the notes view's details and its dialogs, and keep the app's view memory in step with it."""
    result = _notes_view_change(phrase)
    _sync_view()
    return result


def _sync_view() -> None:
    set_view(NOTES_VIEW if _notes_open else None)  # the notes view is a view: it adds its words to the screen's


def _notes_view_change(phrase: str) -> str:
    """The state changes here; the clicks run in the background."""
    global _notes_open, _dialog, _notes_from
    after_play = False
    then_now = False
    if phrase in NOTES_NUMBER:
        number = NOTES_NUMBER[phrase]
        target = COURSE_LIST.point(number, "notes")
        _notes_open, _dialog = True, None
        _notes_from = current_screen()
        scan_notes_view_async()
    elif phrase == "read more" and _notes_open and _dialog is None:
        target, _dialog = READ_MORE, "read_more"
    elif phrase == "latest scores" and _notes_open and _dialog is None:
        target, _dialog = ROUND_HISTORY, "latest_scores"
    elif phrase == "cancel" and _notes_open and _dialog is None and not notes_view_has_cancel():
        return f"{phrase}: no cancel button on this screen"
    elif phrase == "cancel" and (_notes_open or _dialog is not None):
        if _dialog == "latest_scores":
            target, _dialog = HISTORY_CLOSE, None
        elif _dialog == "read_more":
            target, _dialog = DESCRIPTION_CLOSE, None
        else:
            target, _notes_open = PANEL_CLOSE, False
    elif phrase == "close" and _dialog == "read_more":
        target, _dialog = DESCRIPTION_CLOSE, None
    elif phrase in ("play course", "play course now") and _notes_open and _dialog is None:
        target, _notes_open = PANEL_PLAY, False
        after_play = True  # round settings opens; "play course now" also presses its PLAY
        then_now = phrase == "play course now"
    else:
        return f"{phrase}: not in the notes view"
    threading.Thread(
        target=_notes_view_click, args=(target, phrase, after_play, then_now), daemon=True, name="ditch-your-keyboard-notes"
    ).start()
    return f"{phrase}: working"


def _notes_view_click(target: tuple[float, float], phrase: str, after_play: bool, then_now: bool) -> None:
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
_help_pause: Callable[[], None] | None = None  # the listener's: takes the overlay boxes down while the rows are read or clicked
_help_resume: Callable[[], None] | None = None  # and puts them back
SCAN_SETTLE_SECONDS = 0.15  # the overlay boxes take a moment to come down before the rows are read


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
    return COURSE_LIST.state(number)


# The big Play button on the notes panel, sampled at its left edge (blue). On the filter panel this spot is the
# background, so a background reading means the filter panel is up. Read from the Additional Driving Ranges screen.
NOTES_PLAY = (0.705, 0.867)
LIST_MODE: str | None = None  # set when the rows are read: "notes" (the notes view's preview) or "filter" (the filter view)


def scan_rows() -> None:
    """Reads each row's button from the screen. Blue is Play, grey is Download, anything else is an empty row."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return
    rect = client_rect(hwnd)
    COURSE_LIST.read_states(rect)
    log.info("rows: %s", " ".join(f"{number}={COURSE_LIST.state(number) or 'empty'}" for number in COURSE_LIST.states))
    global LIST_MODE
    x, y = _point(rect, NOTES_PLAY)
    LIST_MODE = "notes" if classify_button(*pixel_colour(x, y)) is not None else "filter"
    log.info("list mode: %s", LIST_MODE)
    if LIST_MODE == "filter":
        set_view(FILTER_VIEW)  # the screen itself says which view is up
    elif current_view() == FILTER_VIEW:
        set_view(None)


def list_mode() -> str | None:
    """"notes" or "filter": which view the course list was in when it was last read, or None if not read yet."""
    return LIST_MODE


def scan_rows_async() -> None:
    """Takes the overlay boxes down, reads the rows, then puts the overlay back as the screen is now."""
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
            red, green, blue = pixel_colour(x, y)
            if max(red, green, blue) > 200 and max(red, green, blue) - min(red, green, blue) < 40:
                return True  # white-ish: typed text
    return False


def _row_then_done(action, *args) -> None:
    """Runs a row command, then puts the overlay back. The rows are read again only on "overlay refresh"."""
    try:
        action(*args)
    finally:
        _resume()


def _row_number(phrase: str) -> int | None:
    """The row a phrase is for: "play row one now" is row 1. None for phrases that are not about one row."""
    words = phrase.split()
    word = words[-2] if words[-1] == "now" and len(words) > 1 else words[-1]
    return COURSE_LIST.number(word) if word in COURSE_LIST.rows else None


def _ruled_out(phrase: str) -> str | None:
    """A row command the rows as they are cannot do: the reason to say, and no click. None when it can be done,
    or when the rows have not been read yet."""
    if not COURSE_LIST.states:
        return None
    number = _row_number(phrase)
    if number is None:
        return None
    state = COURSE_LIST.state(number)
    if phrase.startswith("play row") and state != "play":
        return f"{phrase}: that row has no installed course"
    if phrase.startswith("download row") and state != "download":
        return f"{phrase}: that row is not a download"
    if phrase.startswith("show notes") and state is None:
        return f"{phrase}: that row is empty"
    return None


def handle(phrase: str) -> str:
    """Run one chooser command. Returns the note to show. Letters arrive as NATO words while the filter is on."""
    refused = _ruled_out(phrase)
    if refused is not None:
        _resume()  # the listener may have taken the help down for this row; it was not clicked, so it comes back
        return refused
    if phrase in NOTES_NUMBER or phrase in NOTES_VIEW_PHRASES:
        return notes_view_action(phrase)
    if phrase == "show filters":
        return show_filters()
    if phrase == f"use filter":
        return start_filter()
    if phrase == "end filter":
        return end_filter()
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
    """After each letter: say how many courses still match (name, location or designer, as GSPro's filter does).
    When one matches, the note names it. Typing does not stop: the filter is ended by "end filter" only."""
    typed = text_entry.typed()
    if not _key(typed):
        return f"Filter: {typed}"
    matches = courses_matching(typed)
    if not matches:
        return f"Filter: {typed}: no course matches"
    if len(matches) == 1:
        return f"Filter: {typed}: one course, {matches[0]}. Say play row one or show notes one"
    return f"Filter: {typed} ({len(matches)} courses)"


def show_filters() -> str:
    """Click the FILTERS button (it shows at the upper right once the screen has started), which swaps the notes
    view for the filter view. The overlay follows the mode."""
    global LIST_MODE, _notes_open, _dialog
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        return "show filters: GSPro not in front"
    click(*_point(client_rect(hwnd), FILTERS_BUTTON), "show filters: FILTERS button")
    LIST_MODE = "filter"  # the filter view is up now; the overlay switches to the filter boxes
    _notes_open, _dialog = False, None  # the notes view and the filter view share the space: the notes view is gone now
    set_view(FILTER_VIEW)  # its own view now: its four filter words listen
    return "Filters view"


def start_filter() -> str:
    if current_screen() != "on_course":
        return f"use filter: say on course practice first"
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        return f"use filter: GSPro not in front"
    click(*_point(client_rect(hwnd), SEARCH_BOX), f"use filter: search box")
    text_entry.start()
    return "Filter on: say a number, a letter or punctuation; say backspace to undo one"


def end_filter() -> str:
    """Stop typing. The list stays as it is, and its rows are read again, since the typing may have changed them."""
    text_entry.stop()  # the rest of the screen listens again
    scan_rows_async()  # the overlay is taken down and put back, as "overlay refresh" does
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
    return f"toggle favorite {number}: working"


def _favorite_now(number: int) -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info(f"toggle favorite %d: GSPro not in front; not clicked", number)
        return
    x, y = _point(client_rect(hwnd), COURSE_LIST.point(number, "favorite"))
    click(x, y, f"toggle favorite {number}")


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
    x, y = _point(rect, COURSE_LIST.point(number, "button"))
    edge_x, edge_y = _point(rect, COURSE_LIST.edge_point(number))
    if not is_play_button(edge_x, edge_y):
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
    x, y = _point(rect, COURSE_LIST.point(number, "button"))
    edge_x, edge_y = _point(rect, COURSE_LIST.edge_point(number))
    if is_play_button(edge_x, edge_y):
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
