"""Chained GSPro clicks for voice commands, from one shared runner.

A sequence is a list of steps. Each step clicks one position in GSPro's window. A step
can also name a watch area: the runner samples that area before the click and waits for
it to change afterwards, so the next click waits for the screen to respond.

To add a command, add an entry to SEQUENCES and a matching phrase in commands.py.
Positions and watch areas are in gspro_ui.py. Every click goes through clicks.click, so
each one logs its label, point, and window in front.

Clicks never move the pointer afterwards. Moving it right after a click cancelled it.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

from app.clicks import click
from app.connector_ui import _point, _rect, find_window
from app.focus import _force_foreground
from app.gspro_ui import (
    BACK_BUTTON,
    CONFIRM_BUTTON,
    END_ROUND_BUTTON,
    GSPRO_TITLE,
    HOME_WATCH,
    MENU_BUTTON,
    PRACTICE_CARD,
    RANGE_CARD,
    WATCH_DIALOG,
    WATCH_MENU,
    WATCH_SCREEN,
)

log = logging.getLogger(__name__)

WATCH_GRID = 8
CHANGE_LEVEL = 15  # average brightness difference that counts as a changed screen
CHANGE_TIMEOUT = 15.0  # give up waiting for a change after this long
POLL_SECONDS = 0.2

_lock = threading.Lock()

# The screen we think GSPro is on, from the sequences that ran. Not read from GSPro, so it
# can be wrong after a manual change, and it is unknown after a restart until a sequence runs.
SCREEN_AFTER: dict[str, str] = {
    "practice screen": "practice",
    "go to range": "range",
    "gspro practice range screen": "range",
    "gspro practice range": "range",
    "home screen": "home",
    "end round": "home",  # a shortcut back to the home screen
}
_screen: str | None = None

# True after "hide ui" until Esc ("show ui"). GSPro shows no buttons while hidden, so a
# sequence shows the interface first. Set by listener.py when it sends those keys.
SHOW_UI_SECONDS = 1.0
_ui_hidden = False


def set_ui_hidden(hidden: bool) -> None:
    global _ui_hidden
    _ui_hidden = hidden


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
    "end round": (
        Step("GAME MENU", MENU_BUTTON, WATCH_MENU),
        Step("END ROUND", END_ROUND_BUTTON, WATCH_DIALOG),
        Step("CONFIRM", CONFIRM_BUTTON),
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


def _wait_for_change(hwnd: int, box, before: list[float], timeout: float = CHANGE_TIMEOUT) -> float | None:
    """Seconds until the watched area changes, or None if it does not change in time."""
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


def run_in_background(name: str, on_done: Callable[[str], None] | None = None) -> str:
    """Start a sequence on a background thread. Returns a note for the status bar at once."""

    def run() -> None:
        note = run_sequence(name)
        if on_done is not None:
            on_done(note)

    threading.Thread(target=run, name=f"gspraudio-{name}", daemon=True).start()
    return f"Running {name}"


def run_sequence(name: str) -> str:
    if not _lock.acquire(blocking=False):
        return "Already running a GSPro sequence"
    try:
        note = _run(name)
        _remember_screen(name, note)
        return note
    finally:
        _lock.release()


def _remember_screen(name: str, note: str) -> None:
    global _screen
    if note.startswith("Already running") or note.startswith("GSPro window not found"):
        return  # nothing was clicked, so the screen is unchanged
    if name == "home screen" and "at home" in note:
        _screen = "home"
    elif note.endswith(": done") and name in SCREEN_AFTER:
        _screen = SCREEN_AFTER[name]
    else:
        _screen = None  # clicked something we do not track; the screen is unknown


def _run(name: str) -> str:
    global _screen
    # Home is not skipped even when the memory says home: a screen we did not track may
    # have a BACK button, and on a real home screen the first BACK click does nothing.
    if name == "home screen" and _screen == "range":
        name = "end round"  # from the range, going home is ending the round
    steps = SEQUENCES[name]
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
        rect = _rect(hwnd)
        before = _watch_grid(rect, step.watch) if step.watch is not None else None
        click(*_point(rect, step.target), f"{name} step {number} {step.label}")
        if step.watch is not None:
            waited = _wait_for_change(hwnd, step.watch, before, step.wait)
            if waited is None:
                log.warning("%s: %s did not change the screen in %.0f s", name, step.label, step.wait)
                return f"{name}: {step.label} did not change the screen; stopped"
            log.info("%s: screen changed %.1f s after %s", name, waited, step.label)
        if number < len(steps) and not _force_foreground(hwnd):
            log.warning("%s: lost GSPro focus after %s", name, step.label)
            return f"{name}: lost GSPro focus after {step.label}; stopped"
    log.info("%s: done in %.1f s", name, time.monotonic() - started)
    return f"{name}: done"
