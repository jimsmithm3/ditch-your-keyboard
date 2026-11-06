"""Put GSPro in front before keystrokes. Keys hit whichever window is focused."""

import ctypes
import logging
import time

import pygetwindow as gw

log = logging.getLogger(__name__)

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32


def prepare_gspro() -> str | None:
    """Focus GSPro. None means it is in front. Otherwise a short reason."""
    try:
        windows = [
            win
            for win in gw.getAllWindows()
            if "gspro" in (win.title or "").lower()
        ]
    except Exception:
        log.exception("could not list windows")
        return "could not list windows"
    if not windows:
        log.info("GSPro window not found")
        return "Can't find GSPro window"

    win = next((item for item in windows if not item.isMinimized), windows[0])
    hwnd = int(win._hWnd)
    if win.isMinimized:
        win.restore()
    if _force_foreground(hwnd):
        time.sleep(0.05)
        log.info("focused %s", win.title)
        return None
    log.info("could not focus %s", win.title)
    return "could not focus GSPro"


def _force_foreground(hwnd: int) -> bool:
    if _user32.GetForegroundWindow() == hwnd:
        return True
    current = _kernel32.GetCurrentThreadId()
    foreground = _user32.GetForegroundWindow()
    foreground_thread = _user32.GetWindowThreadProcessId(foreground, None)
    _user32.AttachThreadInput(foreground_thread, current, True)
    try:
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
    finally:
        _user32.AttachThreadInput(foreground_thread, current, False)
    return _user32.GetForegroundWindow() == hwnd
