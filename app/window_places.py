"""Remember where the main window and the Commands window are, and put them back at startup.

A window's position is saved as "x,y,width,height" in the saved preferences whenever it is moved or
resized, and when it closes. On startup it is put back only if that rectangle still lies on a screen
(a monitor may have been unplugged since).
"""

from PySide6.QtCore import QEvent, QObject, QRect, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from app.prefs import get_pref, set_pref

MAIN_KEY = "main_window_geometry"
COMMANDS_KEY = "commands_window_geometry"
SAVE_DELAY_MS = 500  # a drag saves once it settles, not on every pixel


def restore(widget: QWidget, key: str) -> bool:
    """Put the widget back where it was saved. False if nothing usable was saved or it is off screen."""
    try:
        x, y, width, height = (int(part) for part in get_pref(key, "").split(","))
    except ValueError:
        return False
    rect = QRect(x, y, width, height)
    if not any(screen.availableGeometry().intersects(rect) for screen in QGuiApplication.screens()):
        return False
    widget.setGeometry(rect)
    return True


class _Remember(QObject):
    def __init__(self, widget: QWidget, key: str) -> None:
        super().__init__(widget)
        self._widget = widget
        self._key = key
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.save)

    def save(self) -> None:
        if not self._widget.isVisible() or self._widget.isMinimized():
            return  # a hidden or minimised window has no position worth keeping
        g = self._widget.geometry()
        set_pref(self._key, f"{g.x()},{g.y()},{g.width()},{g.height()}")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            self.save()  # save at once: the window is about to go
        elif event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self._timer.start(SAVE_DELAY_MS)
        return False


def remember(widget: QWidget, key: str) -> None:
    """Save the widget's position whenever it moves, resizes or closes."""
    widget.installEventFilter(_Remember(widget, key))
