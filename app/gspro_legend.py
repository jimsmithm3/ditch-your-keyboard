"""The NATO letters drawn over the GSPro course list while the course filter is on, so the words can be read
in the game. They sit in the open space between the favourite hearts and the Download buttons. Click-through,
and it takes no focus. Look and feel are not final.
"""

import ctypes

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.connector_ui import client_rect, find_window
from app import text_entry
from app.gspro_screens import GRID_WORDS
from app.gspro_ui import GSPRO_TITLE

# The open column, as fractions of the GSPro window's width and height.
LEFT, RIGHT = 0.525, 0.575  # the column the list was first drawn in, centred on the note icon
SHIFT_LEFT_PX = -10  # the list starts this far left of that column; negative moves it right (40 px right of the old 30 px left)
TOP, BOTTOM = 0.10, 0.99  # TOP is the filter box, so the first line ("Filter: ...") sits in it

_widget: QWidget | None = None


def _character(word: str) -> str:
    """The character a punctuation word types, for the list. Parenthesis types both brackets."""
    return text_entry.CHARACTERS[word][0] if word in text_entry.CHARACTERS else "( )"


class _Legend(QWidget):
    def __init__(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.typed = ""

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt name)
        painter = QPainter(self)
        width, height = self.width(), self.height()
        x0, x1 = LEFT * width - SHIFT_LEFT_PX, RIGHT * width - SHIFT_LEFT_PX
        y0, y1 = TOP * height, BOTTOM * height
        font = QFont()
        font.setPointSize(18)  # twice the earlier 9
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(242, 242, 242, 230))
        if text_entry.punctuation():
            top, rows = "show letters", [f"{_character(word)}  {word}" for word in text_entry.PUNCTUATION_WORDS]
        else:
            top, rows = "show punctuation", [f"{chr(ord('A') + i)}  {word}" for i, word in enumerate(GRID_WORDS)]
        lines = [top] + rows  # the typed letters are in the search box
        metrics = painter.fontMetrics()
        # A fixed row height, so the list uses only the space its lines need; it only shrinks to fit the window.
        step = min(metrics.height() + 8, (y1 - y0) / len(lines))
        painter.fillRect(int(x0), int(y0), int(x1 - x0), int(step * len(lines) + 8), QColor(20, 24, 32, 150))
        painter.setPen(QPen(QColor(230, 30, 30), 4))  # the red box round the letters, as in help mode
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(x0), int(y0), int(x1 - x0), int(step * len(lines) + 8))
        painter.setPen(QColor(242, 242, 242, 230))
        for i, line in enumerate(lines):
            baseline = int(y0 + step * (i + 1) - step * 0.3)
            if i == 0:  # the switch is a help label: red background, white text, like the boxes
                painter.fillRect(QRect(int(x0), baseline - metrics.ascent() - 3, metrics.horizontalAdvance(line) + 12, metrics.height() + 6), QColor(160, 20, 20, 147))
                painter.setPen(QColor(255, 255, 255))
            else:
                painter.setPen(QColor(242, 242, 242, 230))
            painter.drawText(int(x0 + 6), baseline, line)
        painter.end()


GW_HWNDPREV = 3  # the window just above another in the stack
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def _place() -> bool:
    """Cover the GSPro window, so the fractions above map onto it, and sit directly above GSPro in the window
    stack (not always on top), so the list shows over GSPro but under our app's windows. Placed in physical
    pixels with Windows directly, as the grid does. False if GSPro is not there."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return False
    left, top, right, bottom = client_rect(hwnd)
    above = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDPREV)
    ctypes.windll.user32.SetWindowPos(
        int(_widget.winId()), above or 0, left, top, right - left, bottom - top, SWP_NOACTIVATE | SWP_SHOWWINDOW
    )
    return True


def show(typed: str) -> None:
    global _widget
    if _widget is None:
        _widget = _Legend()
    _widget.typed = typed
    _widget.show()  # shown first, so the window exists; _place then moves it over GSPro
    if _place():
        _widget.update()
    else:
        _widget.hide()


def refresh(typed: str) -> None:
    if _widget is not None and _widget.isVisible():
        _widget.typed = typed
        _widget.update()


def hide() -> None:
    if _widget is not None:
        _widget.hide()


def apply(state: tuple[bool, str]) -> None:
    """Called on the GUI thread, with what the listener sends: (shown, typed)."""
    shown, typed = state
    if shown:
        show(typed)
    else:
        hide()
