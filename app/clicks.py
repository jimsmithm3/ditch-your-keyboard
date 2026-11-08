"""One mouse-click function for every app click, with a standard debug log line.

Sends the click with SendInput (the newer Windows call) using absolute screen
coordinates over the whole virtual desktop, so monitors left of the primary one
work. Each click logs what was clicked, where, and which window was in front.
"""

import ctypes
import logging
import time
from ctypes import wintypes

log = logging.getLogger(__name__)

_user32 = ctypes.windll.user32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

HOVER_SECONDS = 0.6  # a game raises a card on hover; let that happen before the press
PRESS_SECONDS = 0.4  # hold the button down this long; a game may ignore a click released at once


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


def _virtual_desktop() -> tuple[int, int, int, int]:
    return (
        _user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        _user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def _send(flags: int, x: int = 0, y: int = 0) -> None:
    vx, vy, vw, vh = _virtual_desktop()
    # Absolute coordinates run 0..65535 across the whole virtual desktop.
    nx = round((x - vx) * 65535 / max(vw - 1, 1))
    ny = round((y - vy) * 65535 / max(vh - 1, 1))
    event = _Input(type=INPUT_MOUSE)
    event.u.mi = _MouseInput(nx, ny, 0, flags | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, 0)
    sent = _user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(_Input))
    if sent != 1:
        log.warning("SendInput sent %d of 1 event (flags %#x)", sent, flags)


def _front_title() -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetWindowTextW(_user32.GetForegroundWindow(), buf, 256)
    return buf.value or "(no title)"


def move(x: int, y: int, label: str = "") -> None:
    """Move the pointer only. Used to leave a card so the next screen gets a fresh enter event."""
    log.info("move %s to (%d,%d)", label or "?", x, y)
    _send(MOUSEEVENTF_MOVE, x, y)


def click(x: int, y: int, label: str = "") -> None:
    """Move to (x, y), pause for the hover, then press and release the left button."""
    log.info(
        "click %s at (%d,%d) front=%r",
        label or "?",
        x,
        y,
        _front_title(),
    )
    _send(MOUSEEVENTF_MOVE, x, y)
    time.sleep(HOVER_SECONDS)
    _send(MOUSEEVENTF_LEFTDOWN, x, y)
    time.sleep(PRESS_SECONDS)
    _send(MOUSEEVENTF_LEFTUP, x, y)
