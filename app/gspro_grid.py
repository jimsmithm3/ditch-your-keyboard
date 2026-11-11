"""A lettered grid over the GSPro window, for placing the pointer precisely by voice.

The first grid is 26 by 26, one cell per letter. Say the column word, then the row word. The chosen
cell becomes the new region, and the second grid is 10 by 10 inside it. Say the column and row again.
After the second pick, the centre of that cell is the point. Positions are fractions of the GSPro window.
The overlay is click-through and takes no focus. Look and feel are not final.
"""

import ctypes
import logging
from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.clicks import click
from app.connector_ui import _point, _rect, find_window
from app.focus import _force_foreground
from app.gspro_overlay import set_status
from app.gspro_screens import GRID_WORDS
from app.gspro_ui import BALL_ICON, GSPRO_TITLE

log = logging.getLogger(__name__)

LEVEL_CELLS = (26, 10)  # cells per side for each pass: 26 by 26, then 10 by 10 inside the chosen cell
LEVELS = len(LEVEL_CELLS)
GRID_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # the letter on each cell; the words are in gspro_screens
Region = tuple[float, float, float, float]  # left, top, right, bottom, as fractions of the GSPro window
FULL: Region = (0.0, 0.0, 1.0, 1.0)

_overlay: QWidget | None = None
_region: Region = FULL
_level = 0
_first: int | None = None  # the column word, waiting for its row word
_on_final: Callable[[float, float], None] | None = None


class _Overlay(QWidget):
    """Draws the grid for the current region over the whole GSPro window."""

    def __init__(self) -> None:
        # Not always on top: _place puts it directly above GSPro in the window stack, so our app's
        # windows stay above the grid where they overlap GSPro.
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.region: Region = FULL
        self.level = 0  # which pass is showing: 0 is the 26 by 26 grid, 1 the 10 by 10

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt name)
        cells = LEVEL_CELLS[self.level]
        left, top, right, bottom = self.region
        width, height = self.width(), self.height()
        x0, y0 = left * width, top * height
        w, h = (right - left) * width, (bottom - top) * height
        cell_w, cell_h = w / cells, h / cells
        painter = QPainter(self)
        pen = QPen(QColor(255, 255, 255, 140))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(cells + 1):
            x = x0 + cell_w * i
            painter.drawLine(int(x), int(y0), int(x), int(y0 + h))
            y = y0 + cell_h * i
            painter.drawLine(int(x0), int(y), int(x0 + w), int(y))
        font = QFont()
        font.setPointSize(9 if self.level == 0 else 7)  # the 26 by 26 pass shows full words, so it is smaller
        font.setBold(True)
        painter.setFont(font)
        black = QColor(0, 0, 0, 230)
        white = QColor(255, 255, 255, 230)
        metrics = painter.fontMetrics()
        for i in range(cells):
            label = GRID_WORDS[i] if self.level == 0 else GRID_LABELS[i]  # full NATO words on the 26 by 26 pass
            text_w = metrics.horizontalAdvance(label)
            col_x = int(x0 + cell_w * i + cell_w / 2 - text_w / 2)
            row_y = int(y0 + cell_h * i + cell_h / 2 + 6)
            # column labels: black along the top, white along the bottom. Row labels: black on the left, white on the right.
            painter.setPen(black)
            painter.drawText(col_x, int(y0 + 18), label)
            painter.drawText(int(x0 + 6), row_y, label)
            painter.setPen(white)
            painter.drawText(col_x, int(y0 + h - 8), label)
            painter.drawText(int(x0 + w - text_w - 6), row_y, label)
        painter.end()


def _ensure() -> None:
    global _overlay
    if _overlay is None:
        _overlay = _Overlay()


SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
GW_HWNDPREV = 3  # the window just above another in the stack


def _place() -> bool:
    """Cover the GSPro window with the overlay, directly above GSPro in the window stack. False if GSPro
    is not there. Placed in physical pixels with Windows directly, since Qt converts positions with each
    screen's scaling. (Not yet verified on a second monitor.)"""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return False
    left, top, right, bottom = _rect(hwnd)  # physical pixels
    # SetWindowPos puts the window BELOW the handle it is given, so give it the window just above GSPro
    # (0 means the top of the stack). Then the grid is above GSPro and below our app's windows.
    above = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDPREV)
    insert_after = above or 0
    ctypes.windll.user32.SetWindowPos(
        int(_overlay.winId()), insert_after, left, top, right - left, bottom - top, SWP_NOACTIVATE | SWP_SHOWWINDOW
    )
    return True


def start(on_final: Callable[[float, float], None] | None = None) -> None:
    global _region, _level, _first, _on_final
    _ensure()
    _region, _level, _first = FULL, 0, None
    _on_final = on_final or _click_point
    if not _place():
        log.info("grid: GSPro window not found")
        return
    _overlay.region = _region
    _overlay.level = 0
    _overlay.update()
    _overlay.show()  # shown first, so the position set below is not overwritten by Qt
    _place()


def stop() -> None:
    global _first, _level, _region
    _first, _level, _region = None, 0, FULL
    if _overlay is not None:
        _overlay.hide()


def is_showing() -> bool:
    return _overlay is not None and _overlay.isVisible()


def pick(index: int) -> None:
    """One word. The first is the column, the second the row; the cell is then the new region.
    A word past the end of the current grid (for example "tango" on the 10 by 10) is ignored."""
    global _region, _level, _first
    if not is_showing():
        return
    cells = LEVEL_CELLS[_level]
    if index >= cells:
        log.info("grid: %d is past the %d by %d grid; ignored", index, cells, cells)
        return
    if _first is None:
        _first = index
        return
    column, row = _first, index
    _first = None
    left, top, right, bottom = _region
    cell_w, cell_h = (right - left) / cells, (bottom - top) / cells
    _region = (left + column * cell_w, top + row * cell_h, left + (column + 1) * cell_w, top + (row + 1) * cell_h)
    _level += 1
    if _level < LEVELS:
        _overlay.region = _region
        _overlay.level = _level
        _overlay.update()
        return
    cx = (_region[0] + _region[2]) / 2
    cy = (_region[1] + _region[3]) / 2
    stop()
    if _on_final is not None:
        _on_final(cx, cy)


def _click_point(x: float, y: float) -> None:
    """The final click: the point picked on the grid, in GSPro window fractions."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("place ball: GSPro not in front; not clicked")
        return
    click(*_point(_rect(hwnd), (x, y)), "place ball: grid point")
    set_status(f"Ball placed at x {x:.3f}, y {y:.3f}")


def _place_ball() -> None:
    """Click the ball icon (placement mode), then pick the point on the grid. The point is clicked."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("place ball: GSPro not in front; not started")
        return
    click(*_point(_rect(hwnd), BALL_ICON), "place ball: ball icon")
    start(on_final=_click_point)


def _cancel() -> None:
    """Close the grid and click the ball icon again, which backs out of placement mode."""
    stop()
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("cancel grid: GSPro not in front; not clicked")
        return
    click(*_point(_rect(hwnd), BALL_ICON), "cancel grid: ball icon")
    set_status("Grid cancelled")


def handle(event: tuple[str, int | None]) -> None:
    """Runs on the GUI thread. event is ("show", None), ("close", None), ("cancel", None), ("pick", index),
    or ("place", None). The index is the word's place in GRID_WORDS."""
    action, value = event
    if action == "show":
        start()
    elif action == "close":
        stop()
    elif action == "cancel":
        _cancel()
    elif action == "pick" and value is not None:
        pick(value)
    elif action == "place":
        _place_ball()
