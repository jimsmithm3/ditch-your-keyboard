"""Finish SQG-GSPRO-Connect's setup for "please play golf": Scan, Connect the LM, Connect GSPro.

The connector exposes no accessibility tree and no native child controls, so this
clicks at positions inside its window. Each position is a fraction of the window
size, read from screenshots of the app's layout (see the constants below).

Windows are placed before clicking. The connector goes to the top-left of its
monitor and the APIv1 Connect window to the bottom-right, so APIv1 cannot cover
the connector's buttons when it pops up.

Safety rules:
- A click happens only after the connector is confirmed to be in front.
- The status lights are read from the screen. A button is clicked only when its
  light is not green, so a connected LM or GSPro is never disconnected by mistake.
- The whole sequence runs on a background thread, because it waits on the apps.
"""

import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable

from app.clicks import click
from app.focus import _force_foreground
from app.launch import _process_running

log = logging.getLogger(__name__)

# Some windows can be checked under a number of titles. The connector's is exact.
TITLE = "SQG-GSPRO-Connect"
APIV1_TITLE = "APIv1 Connect"

# Fractions of the window (left, top at 0,0; right, bottom at 1,1), from the app's layout.
SCAN = (0.061, 0.270)
LM_CONNECT = (0.353, 0.270)
LM_LIGHT = (0.436, 0.273)
GSPRO_CONNECT = (0.353, 0.373)
GSPRO_LIGHT = (0.436, 0.366)

MARGIN = 40  # pixels from the monitor's work-area edges
STACK_GAP = 6  # pixels between the connector and the APIv1 window under it
SETTLE_SECONDS = 3.0  # the window can show before the app is ready for clicks
SCAN_WAIT_SECONDS = 6.0  # time for the scan to find the LM and fill the drop-down
LM_WAIT_SECONDS = 20.0
GSPRO_WAIT_SECONDS = 30.0
WINDOW_WAIT_SECONDS = 30.0  # the connector window can take a moment after it is started
APIV1_WAIT_SECONDS = 30.0  # APIv1 Connect opens about 10 seconds after GSPro
GSPRO_UP_WAIT_SECONDS = 90.0  # GSPro is started first, but it takes a while to load

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32

# Window rects and screen pixels must use the same units. At 125% or 150% scaling an
# unaware process gets scaled window rects but real pixel reads, so the lights look red.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor; harmless if already set
except (AttributeError, OSError):
    pass

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MONITOR_DEFAULTTONEAREST = 2
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

_EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_busy = threading.Lock()


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def find_window(title: str = TITLE) -> int | None:
    found: list[int] = []

    def callback(hwnd, _):
        if _user32.IsWindowVisible(hwnd) and _window_title(hwnd) == title:
            found.append(hwnd)
        return True

    _user32.EnumWindows(_EnumProc(callback), 0)
    return found[0] if found else None


def _rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _point(rect: tuple[int, int, int, int], fraction: tuple[float, float]) -> tuple[int, int]:
    left, top, right, bottom = rect
    return round(left + (right - left) * fraction[0]), round(top + (bottom - top) * fraction[1])


def _work_area(hwnd: int) -> wintypes.RECT:
    """The usable area (without the taskbar) of the monitor the window is on."""
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(_MonitorInfo)
    monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    _user32.GetMonitorInfoW(monitor, ctypes.byref(info))
    return info.rcWork


def _move(hwnd: int, x: int, y: int) -> None:
    _user32.SetWindowPos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


def place_windows() -> None:
    """Connector at the top-left of its monitor, APIv1 Connect directly under it."""
    connector = find_window()
    if connector is None:
        return
    work = _work_area(connector)
    left, top = work.left + MARGIN, work.top + MARGIN
    _move(connector, left, top)
    apiv1 = find_window(APIV1_TITLE)
    if apiv1 is not None:
        _, _, _, connector_bottom = _rect(connector)
        _move(apiv1, left, connector_bottom + STACK_GAP)
    log.info("connector setup: placed windows (APIv1 %s)", "found" if apiv1 else "not open yet")


def _is_green(x: int, y: int) -> bool:
    """The status light is green when its pixel is clearly green (COLORREF is 0x00BBGGRR)."""
    dc = _user32.GetDC(0)
    try:
        color = _gdi32.GetPixel(dc, x, y)
    finally:
        _user32.ReleaseDC(0, dc)
    red = color & 0xFF
    green = (color >> 8) & 0xFF
    blue = (color >> 16) & 0xFF
    return green > 150 and red < 120 and blue < 120


def _click(x: int, y: int, label: str = "connector") -> None:
    click(x, y, label)


def _wait_for(check: Callable[[], bool], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.5)
    return check()


def _wait_green(light: tuple[int, int], seconds: float) -> bool:
    return _wait_for(lambda: _is_green(*light), seconds)


def lights() -> dict[str, bool] | None:
    """Current LM and GSPro light state, or None when the connector window is not open."""
    hwnd = find_window()
    if hwnd is None:
        return None
    rect = _rect(hwnd)
    return {
        "lm": _is_green(*_point(rect, LM_LIGHT)),
        "gspro": _is_green(*_point(rect, GSPRO_LIGHT)),
    }


def finish_setup() -> str:
    """Click through the setup. Returns a short note for the status bar."""
    if not _busy.acquire(blocking=False):
        return "Connector setup is already running"
    try:
        return _finish_setup()
    finally:
        _busy.release()


def _connector_rect() -> tuple[int, int, int, int, int] | None:
    """(hwnd, left, top, right, bottom) of the connector, or None."""
    hwnd = find_window()
    if hwnd is None:
        return None
    return (hwnd, *_rect(hwnd))


def _focus_and_rect() -> tuple[int, int, int, int] | None:
    """Re-place the windows, bring the connector to the front, and return its rect.
    None when the connector cannot be made the front window, so no click is sent."""
    place_windows()
    found = _connector_rect()
    if found is None:
        return None
    hwnd, left, top, right, bottom = found
    if not _force_foreground(hwnd):
        return None
    return left, top, right, bottom


def _finish_setup() -> str:
    if not _wait_for(lambda: find_window() is not None, WINDOW_WAIT_SECONDS):
        return "SQG-GSPRO-Connect window did not appear"
    # Wait for APIv1 so it is placed before it can cover the connector.
    _wait_for(lambda: find_window(APIV1_TITLE) is not None, APIV1_WAIT_SECONDS)

    rect = _focus_and_rect()
    if rect is None:
        log.warning("connector setup: could not bring %s to the front", TITLE)
        return "could not bring SQG-GSPRO-Connect to the front; setup not done"
    notes = []

    if _is_green(*_point(rect, LM_LIGHT)):
        notes.append("LM already connected")
    else:
        time.sleep(SETTLE_SECONDS)
        rect = _focus_and_rect()
        if rect is None:
            return "lost the connector window before Scan; stopped"
        _click(*_point(rect, SCAN))
        log.info("connector setup: clicked Scan")
        time.sleep(SCAN_WAIT_SECONDS)
        time.sleep(SETTLE_SECONDS)
        rect = _focus_and_rect()
        if rect is None:
            return "; ".join(notes + ["lost the connector window before Connect (LM); stopped"])
        _click(*_point(rect, LM_CONNECT))
        log.info("connector setup: clicked Connect (LM)")
        if _wait_green(_point(rect, LM_LIGHT), LM_WAIT_SECONDS):
            notes.append("LM connected")
        else:
            notes.append("LM did not connect")

    if _is_green(*_point(rect, GSPRO_LIGHT)):
        notes.append("GSPro already connected")
    else:
        if not _wait_for(lambda: _process_running("GSpro.exe"), GSPRO_UP_WAIT_SECONDS):
            notes.append("GSPro is not running, so GSPro was not connected")
            note = "; ".join(notes)
            log.info("connector setup: %s", note)
            return note
        time.sleep(SETTLE_SECONDS)
        rect = _focus_and_rect()
        if rect is None:
            return "; ".join(notes + ["lost the connector window before Connect (GSPro); stopped"])
        _click(*_point(rect, GSPRO_CONNECT))
        log.info("connector setup: clicked Connect (GSPro)")
        if _wait_green(_point(rect, GSPRO_LIGHT), GSPRO_WAIT_SECONDS):
            notes.append("GSPro connected")
        else:
            notes.append("GSPro did not connect (is GSPro up?)")

    note = "; ".join(notes)
    log.info("connector setup: %s", note)
    return note


def finish_setup_in_background(on_done: Callable[[str], None] | None = None) -> None:
    def run() -> None:
        note = finish_setup()
        if on_done is not None:
            on_done(note)

    threading.Thread(target=run, name="gspraudio-connector-setup", daemon=True).start()
