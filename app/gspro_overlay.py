"""A quiet status line drawn over the bottom middle of the GSPro window: the app's status and what was
last heard. It is click-through and does not take focus, so it never blocks a click or takes the keyboard.
Gated by the GSPro Overlay preference (on by default).

With Debug Mode on (the default), a second box sits to the right of the status line and lists the
grammars listening right now, updated as they change. Look, feel, and wording are not final.
"""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel

from app.connector_ui import _rect, find_window
from app.gspro_ui import GSPRO_TITLE
from app.prefs import get_pref

PREF_KEY = "gspro_overlay"
DEBUG_PREF_KEY = "debug_mode"
BOTTOM_OFFSET = 90  # logical pixels between the line and the GSPro window's bottom edge
DEBUG_GAP = 12  # logical pixels between the debug box and the left edge of the status line
REFRESH_MS = 500  # keeps the line on GSPro when the window moves or appears

_label: QLabel | None = None
_debug: QLabel | None = None
_timer: QTimer | None = None
_status = ""
_heard = ""
_grammars: list[str] = []


def enabled() -> bool:
    return get_pref(PREF_KEY, "True") == "True"


def debug_enabled() -> bool:
    return get_pref(DEBUG_PREF_KEY, "True") == "True"


def _text() -> str:
    parts = [part for part in (_status, f"Heard: {_heard}" if _heard else "") if part]
    return "   |   ".join(parts)


def _flags():
    return (
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.WindowDoesNotAcceptFocus
        | Qt.WindowType.WindowTransparentForInput
    )


def _ensure() -> None:
    global _label, _debug, _timer
    if _label is not None:
        return
    _label = QLabel(None, _flags())
    _label.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    _label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    _label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    _label.setStyleSheet(
        "QLabel { background: rgba(20, 24, 32, 150); color: #f2f2f2; padding: 6px 12px; font-size: 16px; border-radius: 6px; }"
    )
    _debug = QLabel(None, _flags())
    _debug.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    _debug.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    _debug.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    _debug.setStyleSheet(
        "QLabel { background: rgba(20, 24, 32, 150); color: #f2f2f2; padding: 6px 10px; font-size: 13px; border-radius: 6px; }"
    )
    _timer = QTimer(_label)
    _timer.timeout.connect(_refresh)
    _timer.start(REFRESH_MS)


def _place() -> bool:
    """Find GSPro and put the status line over its bottom middle. False if GSPro is not there."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return False
    left, _top, right, bottom = _rect(hwnd)  # physical pixels
    screen = QGuiApplication.screenAt(QPoint(left, bottom)) or QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() or 1.0
    centre_x = (left + right) / 2 / ratio
    bottom_y = bottom / ratio
    _label.move(int(centre_x - _label.width() / 2), int(bottom_y - BOTTOM_OFFSET - _label.height()))
    return True


def _refresh_debug() -> None:
    """The grammar list, to the right of the status line."""
    if not (debug_enabled() and _grammars):
        _debug.hide()
        return
    _debug.setText("<b>Listening</b><br>" + "<br>".join(_grammars))
    _debug.adjustSize()
    _debug.move(_label.x() - DEBUG_GAP - _debug.width(), _label.y())  # to the left of the status line
    _debug.show()


def _refresh() -> None:
    if _label is None:
        return
    if not _place():
        _label.hide()
        _debug.hide()
        return
    text = _text() if enabled() else ""
    if text:
        _label.setText(text)
        _label.adjustSize()
        _place()  # the width is known now, so centre it
        _label.show()
    else:
        _label.hide()
    _refresh_debug()


def set_status(text: str) -> None:
    global _status
    _status = text
    _ensure()
    _refresh()


def set_heard(text: str) -> None:
    global _heard
    _heard = text
    _ensure()
    _refresh()


def set_grammars(names: list[str]) -> None:
    """The grammars listening right now, by readable name."""
    global _grammars
    _grammars = list(names)
    _ensure()
    _refresh()
