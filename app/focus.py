"""Put GSPro in front before keystrokes. Keys hit whichever window is focused."""

import ctypes
import logging
import time

import pygetwindow as gw

log = logging.getLogger(__name__)

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

GSPRO_WINDOW_TITLE = "GSPro"  # the window title GSPro itself uses; same text as gspro_ui.GSPRO_TITLE

# Test mode (Developer page) turns this off so a minimized GSPro stays minimized.
_restore_minimized = True


def set_restore_minimized(flag: bool) -> None:
    global _restore_minimized
    _restore_minimized = flag


def prepare_gspro() -> str | None:
    """Focus GSPro. None means it is in front. Otherwise a short reason."""
    try:
        # The title must be exactly "GSPro". A browser tab whose page title starts with "gspro" (for example
        # "gspro shotcam ... - Google Chrome") and this app's own windows were getting the keys. find_window in
        # connector_ui matches the same exact title.
        windows = [win for win in gw.getAllWindows() if (win.title or "") == GSPRO_WINDOW_TITLE]
    except Exception:
        log.exception("could not list windows")
        return "could not list windows"
    if not windows:
        log.info("GSPro window not found")
        return "Can't find GSPro window"

    win = next((item for item in windows if not item.isMinimized), windows[0])
    hwnd = int(win._hWnd)
    if win.isMinimized:
        if not _restore_minimized:
            log.info("GSPro is minimized; test mode leaves it alone")
            return "GSPro is minimized (test mode)"
        win.restore()
    if _force_foreground(hwnd):
        time.sleep(0.05)
        log.info("focused %s", win.title)
        return None
    log.info("could not focus %s", win.title)
    return "could not focus GSPro"


def gspro_in_front() -> bool:
    """True when the window in front is GSPro (same exact title rule as prepare_gspro)."""
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetWindowTextW(_user32.GetForegroundWindow(), buf, 256)
    return buf.value == GSPRO_WINDOW_TITLE


def ensure_gspro() -> str | None:
    """Keys go to GSPro only. Focus GSPro again if something else took the front.
    None means GSPro is in front. Otherwise a short reason, and no key should be sent."""
    if gspro_in_front():
        return None
    return prepare_gspro()


VK_MENU = 0x12  # Alt
KEYEVENTF_KEYUP = 0x0002


def _front_title() -> str:
    buf = ctypes.create_unicode_buffer(256)
    _user32.GetWindowTextW(_user32.GetForegroundWindow(), buf, 256)
    return buf.value or "(no title)"


def _alt_tap() -> None:
    """Windows only lets a background app take the front right after input. An Alt tap
    counts as that input. GSPro does not use Alt, so the tap does nothing there."""
    _user32.keybd_event(VK_MENU, 0, 0, 0)
    _user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)


def _try_front(hwnd: int) -> bool:
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


def _force_foreground(hwnd: int) -> bool:
    if _user32.GetForegroundWindow() == hwnd:
        return True
    for attempt in range(3):
        if _try_front(hwnd):
            return True
        if attempt == 0:
            _alt_tap()
        time.sleep(0.05)
    log.info("front window was %r when GSPro could not be focused", _front_title())
    return False
