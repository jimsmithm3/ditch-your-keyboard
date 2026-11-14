"""Debug command "debug press": one isolated press on a GSPro card per voice command.

Each time the command is said, the next test in CASES runs once, on its own. There is
no chaining, so a result is never mixed up with the click before it. The log line for
each run names the case, so a result can be matched to what happened on screen.

Use it on the GSPro practice screen. The target is the GSPRO PRACTICE RANGE card.
"""

import ctypes
import logging
import threading
import time
from typing import Callable

from app import clicks
from app.clicks import MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_MOVE
from app.connector_ui import _point, client_rect, find_window
from app.focus import _force_foreground
from app.gspro_ui import GSPRO_TITLE, RANGE_CARD

log = logging.getLogger(__name__)

_user32 = ctypes.windll.user32
_lock = threading.Lock()
_next_case = 0


def _sendinput_press(x: int, y: int, hover: float, hold: float) -> None:
    clicks._send(MOUSEEVENTF_MOVE, x, y)
    time.sleep(hover)
    clicks._send(MOUSEEVENTF_LEFTDOWN, x, y)
    time.sleep(hold)
    clicks._send(MOUSEEVENTF_LEFTUP, x, y)


def _legacy_press(x: int, y: int, hover: float, hold: float) -> None:
    """The older mouse_event call, with the same timing as the others."""
    _user32.SetCursorPos(x, y)
    time.sleep(hover)
    _user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(hold)
    _user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


# (name, function(x, y)) — one test per voice command, in this order.
CASES: list[tuple[str, Callable[[int, int], None]]] = [
    ("SendInput hover 0.6 hold 0.4", lambda x, y: _sendinput_press(x, y, 0.6, 0.4)),
    ("SendInput no hover hold 0.05", lambda x, y: _sendinput_press(x, y, 0.0, 0.05)),
    ("SendInput hover 1.5 hold 0.4", lambda x, y: _sendinput_press(x, y, 1.5, 0.4)),
    ("SendInput hover 0.6 hold 0.1", lambda x, y: _sendinput_press(x, y, 0.6, 0.1)),
    ("mouse_event hover 0.6 hold 0.4", lambda x, y: _legacy_press(x, y, 0.6, 0.4)),
    ("SendInput hover 0.6 hold 1.0", lambda x, y: _sendinput_press(x, y, 0.6, 1.0)),
]


def debug_press_in_background(on_done: Callable[[str], None] | None = None) -> str:
    def run() -> None:
        note = debug_press()
        if on_done is not None:
            on_done(note)

    threading.Thread(target=run, name="gspraudio-debug-press", daemon=True).start()
    return "Debug press running"


def range_press() -> str:
    """The press that works by hand, for "practice range": case 1 every time, not cycled."""
    return _run_case(0)


def range_press_in_background(on_done: Callable[[str], None] | None = None) -> str:
    def run() -> None:
        note = range_press()
        if on_done is not None:
            on_done(note)

    threading.Thread(target=run, name="gspraudio-practice-range", daemon=True).start()
    return "Going to the practice range"


def debug_press() -> str:
    global _next_case
    index = _next_case % len(CASES)
    _next_case += 1
    return _run_case(index)


def _run_case(index: int) -> str:
    if not _lock.acquire(blocking=False):
        return "Debug press already running"
    try:
        name, press = CASES[index]

        hwnd = find_window(GSPRO_TITLE)
        if hwnd is None:
            return "GSPro window not found"
        if not _force_foreground(hwnd):
            return "could not bring GSPro to the front; not pressed"

        x, y = _point(client_rect(hwnd), RANGE_CARD)
        log.info(
            "debug press case %d/%d: %s | target (%d,%d) rect %s front=%r",
            index + 1,
            len(CASES),
            name,
            x,
            y,
            client_rect(hwnd),
            clicks._front_title(),
        )
        press(x, y)
        log.info("debug press case %d/%d done", index + 1, len(CASES))
        return f"Debug press {index + 1}/{len(CASES)}: {name}"
    finally:
        _lock.release()
