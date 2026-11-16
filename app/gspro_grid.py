"""A lettered grid over the GSPro window, for placing the pointer precisely by voice.

The first grid is 26 by 26, one cell per letter. Say the column word, then the row word. The chosen
cell becomes the new region, and the second grid is 4 by 4 inside it. Say the column and row again.
After the second pick, the centre of that cell is the point. Positions are fractions of the GSPro window.
The overlay is click-through and takes no focus. Look and feel are not final.
"""

import ctypes
import logging
import time
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.clicks import click, move
from app.commands import press_keys
from app.connector_ui import _point, client_rect, find_window
from app.focus import _force_foreground
from app.gspro_overlay import set_status
from app.gspro_settings import map_side
from app.gspro_screens import GRID_WORDS
from app.gspro_ui import BALL_ICON, GSPRO_TITLE, MAP_EXPANDED_BOUNDS, MAP_SMALL_BOUNDS

log = logging.getLogger(__name__)

LEVEL_CELLS = (26, 4)  # cells per side for each pass: 26 by 26, then 4 by 4 inside the chosen cell
LEVELS = len(LEVEL_CELLS)
GRID_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # the letter on each cell; the words are in gspro_screens
Region = tuple[float, float, float, float]  # left, top, right, bottom, as fractions of the GSPro window
FULL: Region = (0.0, 0.0, 1.0, 1.0)

_overlay: QWidget | None = None
_region: Region = FULL
_level = 0
_first: int | None = None  # the column word, waiting for its row word
_undo: list[tuple[Region, int, int | None]] = []  # the region, pass and column waiting for a row, before each word
_on_final: Callable[[float, float], None] | None = None


COLUMN_SHADE = QColor(200, 200, 200, 40)  # a very light grey, see-through: every other column, or the one said
CHECKER_SHADE = QColor(200, 200, 200, 150)  # the 4 by 4 checkerboard: less see-through, so it shows over the course


def _draw_vertical(painter: QPainter, text: str, x: float, y: float, reads_down: bool) -> None:
    """Draw text turned a quarter turn. reads_down: it starts at (x, y) and runs down the window, with its
    top to the right. Otherwise it starts at (x, y) and runs up, with its top to the left."""
    painter.save()
    painter.translate(x, y)
    painter.rotate(90 if reads_down else -90)
    painter.drawText(0, 0, text)
    painter.restore()


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
        self.level = 0  # which pass is showing: 0 is the 26 by 26 grid, 1 the 4 by 4
        self.highlight: int | None = None  # the column just called out, waiting for its row; shaded alone

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt name)
        cells = LEVEL_CELLS[self.level]
        left, top, right, bottom = self.region
        width, height = self.width(), self.height()
        x0, y0 = left * width, top * height
        w, h = (right - left) * width, (bottom - top) * height
        cell_w, cell_h = w / cells, h / cells
        painter = QPainter(self)
        if self.level == 1 and self.highlight is not None:
            # The 4 by 4 pass after its column is said: only that column, its cells shaded alternately. The other
            # columns are hidden.
            col = self.highlight
            if col < cells:
                col_x = x0 + cell_w * col
                for row in range(cells):
                    if (col + row) % 2 == 0:
                        painter.fillRect(int(col_x), int(y0 + cell_h * row), int(cell_w), int(cell_h), CHECKER_SHADE)
                pen = QPen(QColor(255, 255, 255, 60))
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawLine(int(col_x), int(y0), int(col_x), int(y0 + h))
                painter.drawLine(int(col_x + cell_w), int(y0), int(col_x + cell_w), int(y0 + h))
                for row in range(cells + 1):
                    y = y0 + cell_h * row
                    painter.drawLine(int(col_x), int(y), int(col_x + cell_w), int(y))
            painter.end()
            return
        # The lines are see-through so GSPro shows underneath. The 4 by 4 pass sits close over the cells
        # of the first, so it is fainter than the 26 by 26 but a little less transparent than before.
        line_alpha, label_alpha = (90, 150) if self.level == 0 else (60, 100)
        pen = QPen(QColor(255, 255, 255, line_alpha))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(cells + 1):
            x = x0 + cell_w * i
            # On the 26 by 26 pass, once a column is said only its two edges are drawn: the other column lines are hidden.
            if self.level == 0 and self.highlight is not None and i not in (self.highlight, self.highlight + 1):
                pass
            else:
                painter.drawLine(int(x), int(y0), int(x), int(y0 + h))
            y = y0 + cell_h * i
            painter.drawLine(int(x0), int(y), int(x0 + w), int(y))
        font = QFont()
        font.setPointSize(11 if self.level == 0 else 7)  # the 26 by 26 pass shows full words, so it is smaller
        font.setBold(True)
        painter.setFont(font)
        white = QColor(255, 255, 255, label_alpha)  # the labels, all white and semi-transparent
        painter.setPen(Qt.PenStyle.NoPen)
        if self.level == 1:
            # The 4 by 4 pass has no text: shaded cells in a checkerboard, so the cells can be seen through.
            for col in range(cells):
                for row in range(cells):
                    if (col + row) % 2 == 0:
                        painter.fillRect(
                            int(x0 + cell_w * col), int(y0 + cell_h * row), int(cell_w), int(cell_h), CHECKER_SHADE
                        )
            painter.end()
            return
        if self.highlight is None:
            for i in range(0, cells, 2):  # before a column is said: every other column, so the columns are easy to count
                painter.fillRect(int(x0 + cell_w * i), int(y0), int(cell_w), int(h), COLUMN_SHADE)
        elif self.highlight < cells:
            painter.fillRect(int(x0 + cell_w * self.highlight), int(y0), int(cell_w), int(h), COLUMN_SHADE)  # the column said
        painter.setPen(white)
        metrics = painter.fontMetrics()
        for i in range(cells):
            label = GRID_WORDS[i]  # full NATO words on the 26 by 26 pass
            text_w = metrics.horizontalAdvance(label)
            # Rows count up from the bottom, like a 0,0 origin: alpha (row 0) is the bottom row.
            row_y = int(y0 + cell_h * (cells - 1 - i) + cell_h / 2 + 6)
            centre = x0 + cell_w * i + cell_w / 2  # the column's middle, for the vertical column labels
            ascent = metrics.ascent()
            # Column labels run vertically: along the top reading down, along the bottom reading up.
            # Row labels stay horizontal: on the left and on the right.
            _draw_vertical(painter, label, centre - ascent / 2, y0 + 4, reads_down=True)
            painter.drawText(int(x0 + 6), row_y, label)
            _draw_vertical(painter, label, centre + ascent / 2, y0 + h - 4, reads_down=False)
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
    left, top, right, bottom = client_rect(hwnd)  # physical pixels
    # SetWindowPos puts the window BELOW the handle it is given, so give it the window just above GSPro
    # (0 means the top of the stack). Then the grid is above GSPro and below our app's windows.
    above = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDPREV)
    insert_after = above or 0
    ctypes.windll.user32.SetWindowPos(
        int(_overlay.winId()), insert_after, left, top, right - left, bottom - top, SWP_NOACTIVATE | SWP_SHOWWINDOW
    )
    return True


def start(on_final: Callable[[float, float], None] | None = None, region: Region = FULL) -> None:
    global _region, _level, _first, _on_final
    _ensure()
    _region, _level, _first = region, 0, None
    _undo.clear()
    _on_final = on_final or _click_point
    if not _place():
        log.info("grid: GSPro window not found")
        return
    _overlay.region = _region
    _overlay.level = 0
    _overlay.highlight = None
    _overlay.update()
    _overlay.show()  # shown first, so the position set below is not overwritten by Qt
    _place()


def stop() -> None:
    global _first, _level, _region
    _first, _level, _region = None, 0, FULL
    _undo.clear()
    if _overlay is not None:
        _overlay.highlight = None
    if _overlay is not None:
        _overlay.hide()


def is_showing() -> bool:
    return _overlay is not None and _overlay.isVisible()


def pick(index: int) -> None:
    """One word. The first is the column, the second the row; the cell is then the new region.
    A word past the end of the current grid (for example "echo" on the 4 by 4) is ignored."""
    global _region, _level, _first
    if not is_showing():
        return
    cells = LEVEL_CELLS[_level]
    if index >= cells:
        log.info("grid: %d is past the %d by %d grid; ignored", index, cells, cells)
        return
    _undo.append((_region, _level, _first))  # so "redo" can take this word back
    if _first is None:
        _first = index
        _overlay.highlight = index  # shade the column just called out
        _overlay.update()
        return
    column, row = _first, cells - 1 - index  # the row word counts up from the bottom, to match the labels
    _first = None
    _overlay.highlight = None
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


def redo() -> None:
    """Take back the last letter, one at a time: each "redo" undoes one more word, so several can be undone in turn.
    Says nothing when there is nothing left to undo."""
    global _region, _level, _first
    if not is_showing():
        return
    if not _undo:
        log.info("grid: redo; nothing to redo")
        return
    _region, _level, _first = _undo.pop()
    _overlay.region = _region
    _overlay.level = _level
    _overlay.highlight = _first
    _overlay.update()
    log.info("grid: redo; pass %d, column %s", _level + 1, _first)


def map_key() -> None:
    """Press S to change the mini map's size, and leave the app's map flag alone. The user says "sync map small" or
    "sync map large" afterwards if the flag no longer matches the screen."""
    press_keys("s")
    log.info("grid: map size key pressed; the app's flag is not changed")


def _click_point(x: float, y: float) -> None:
    """The final click: the point picked on the grid, in GSPro window fractions."""
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("place ball: GSPro not in front; not clicked")
        return
    # Move the cursor onto the point first and let it rest there, so the ball cursor is on the spot before
    # the press. Then click at the same spot.
    point = _point(client_rect(hwnd), (x, y))
    move(*point, "place ball: grid point")
    time.sleep(PLACE_HOVER_SECONDS)
    click(*point, "place ball: grid point")
    set_status(f"Ball placed at x {x:.3f}, y {y:.3f}")


MAP_RESIZE_SECONDS = 0.6  # a settle pause after the S key, so GSPro has finished resizing the mini map
MAP_RESTORE_WAIT_SECONDS = 1.0  # before the S key that makes the map small again, after the ball icon click
PLACE_HOVER_SECONDS = 1.0  # the cursor rests on the picked point before the press, so the ball cursor is there first
SETTLE_SECONDS = 0.5  # a pause between the point click and the ball icon click, so GSPro takes the first one
ZOOM_PAUSE_SECONDS = 0.3  # between the zoom in and zoom out taps, so GSPro sees each one
_placing_flag = False  # True for "place pin": the flag is placed with Shift held, not the ball with Ctrl
_restore_small = False  # True while the map is large only for ball placement; it goes back to small after


def _live_map_state(hwnd: int) -> str:
    """The mini map's size as the screen shows it right now (see app/map_state.py). The game window is copied into
    memory once, and the pixels are read from that copy. Reading each pixel from the screen took seconds."""
    from app.map_state import read_map_state

    left, top, right, bottom = client_rect(hwnd)
    width, height = right - left, bottom - top
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    srccopy = 0x00CC0020
    screen = user32.GetDC(0)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    previous = gdi32.SelectObject(memory, bitmap)
    try:
        gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, srccopy)

        def probe(fx: float, fy: float) -> tuple[int, int, int]:
            x = min(max(int(fx * width), 0), width - 1)
            y = min(max(int(fy * height), 0), height - 1)
            color = gdi32.GetPixel(memory, x, y)
            return (color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF)

        return read_map_state(probe)
    finally:
        gdi32.SelectObject(memory, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(0, screen)


def _map_to_large(hwnd: int) -> bool:
    """Ball placement only works on the large map. The screen decides: if it shows the small map, press S once and
    check again. The app's flag follows what the screen shows. False if DYK cannot tell what it is looking at."""
    global _restore_small
    from app.gspro_sequences import set_map_expanded

    state = _live_map_state(hwnd)
    log.info("place ball: the screen shows the map as %s", state)
    if state == "unknown":
        set_status("DYK is lost: it can't read the mini map. Say sync map small or sync map large, then place ball again.")
        return False
    if state == "large":
        set_map_expanded(True)
        return True
    press_keys("s")
    time.sleep(MAP_RESIZE_SECONDS)
    state = _live_map_state(hwnd)
    set_map_expanded(state == "large")
    if state != "large":
        set_status("DYK is lost: the map did not change size. Say sync map small or sync map large, then place ball again.")
        return False
    _restore_small = True
    return True


def _map_restore() -> None:
    """Put the map back to small if placement made it large."""
    global _restore_small
    if not _restore_small:
        return
    _restore_small = False
    from app.gspro_sequences import toggle_map

    time.sleep(MAP_RESTORE_WAIT_SECONDS)  # a full second, so the ball icon click has settled before the map changes
    press_keys("s")
    toggle_map()


class _CursorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", ctypes.c_void_p),
        ("ptScreenPos", wintypes.POINT),
    ]


def _cursor_is_ball() -> bool:
    """True when Windows shows a cursor that is not the normal arrow, I-beam or hand. GSPro's ball form is one
    of those custom cursors; over GSPro otherwise the cursor is the arrow."""
    info = _CursorInfo()
    info.cbSize = ctypes.sizeof(_CursorInfo)
    if not ctypes.windll.user32.GetCursorInfo(ctypes.byref(info)) or not info.hCursor:
        return False
    user32 = ctypes.windll.user32
    user32.LoadCursorW.restype = ctypes.c_void_p
    user32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    standard = {user32.LoadCursorW(None, ident) for ident in (32512, 32513, 32649)}  # arrow, I-beam, hand
    return info.hCursor not in standard


def _mirror(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """The same box on the other side of the window: left and right swap, top and bottom stay."""
    left, top, right, bottom = bounds
    return 1 - right, top, 1 - left, bottom


def _expanded_bounds() -> tuple[float, float, float, float]:
    """The large map's box for this side of the screen (the left side is a mirror of the right)."""
    return MAP_EXPANDED_BOUNDS if map_side() == "right" else _mirror(MAP_EXPANDED_BOUNDS)


def _small_bounds() -> tuple[float, float, float, float]:
    return MAP_SMALL_BOUNDS if map_side() == "right" else _mirror(MAP_SMALL_BOUNDS)


def _to_small_map(x: float, y: float) -> tuple[float, float]:
    """The same relative spot on the small map as (x, y) is on the large map, both in window fractions."""
    el, et, er, eb = _expanded_bounds()
    sl, st, sr, sb = _small_bounds()
    u, v = (x - el) / (er - el), (y - et) / (eb - et)
    return sl + u * (sr - sl), st + v * (sb - st)


def _toggle_map_size() -> None:
    """Press S and keep the app's map flag in step. Waits for GSPro to finish resizing."""
    from app.gspro_sequences import toggle_map

    press_keys("s")
    toggle_map()
    time.sleep(MAP_RESIZE_SECONDS)


def _finish(x: float, y: float) -> None:
    """The final pick, made on the large map. GSPro seems to ignore a placement outside the small map, so: shrink
    the map, click the same relative spot on the small map with Ctrl held (which places the ball), then expand
    the map again if it was large before placement."""
    global _restore_small
    originally_large = not _restore_small  # if placement had to make the map large, it was small to begin with
    _toggle_map_size()  # shrink for the placement
    _restore_small = False
    sx, sy = _to_small_map(x, y)
    key = "shift" if _placing_flag else "ctrl"  # a flag is placed while Shift is held; a ball while Ctrl is
    log.info("place %s: large map point %.3f, %.3f is small map point %.3f, %.3f", _what(), x, y, sx, sy)
    _hold_key(key, True)
    try:
        _click_point(sx, sy)
        time.sleep(SETTLE_SECONDS)
        ball = _cursor_is_ball()
        log.info("place ball: after the point the cursor is %s", "the ball form" if ball else "a normal cursor")
        if ball:
            _click_point(sx, sy)
            time.sleep(SETTLE_SECONDS)
            log.info(
                "place ball: after the second point the cursor is %s",
                "the ball form" if _cursor_is_ball() else "a normal cursor",
            )
    finally:
        _hold_key(key, False)  # released before the S key, so it is not a Ctrl+S or Shift+S
    if originally_large:
        _toggle_map_size()  # the map was large before placement: make it large again
    _refresh_map()


def _refresh_map() -> None:
    """Zoom in and back out. GSPro's small map does not redraw after a placement until the zoom changes, so this
    refreshes it. (A workaround until the glitch is fixed.)"""
    press_keys("q")  # zoom in
    time.sleep(ZOOM_PAUSE_SECONDS)
    press_keys("w")  # zoom out
    time.sleep(ZOOM_PAUSE_SECONDS)


def _hold_key(name: str, down: bool) -> None:
    import pydirectinput

    if down:
        pydirectinput.keyDown(name)
    else:
        pydirectinput.keyUp(name)


def _what() -> str:
    return "flag" if _placing_flag else "ball"


def _place_ball(flag: bool = False) -> None:
    """Make the map large if needed, click the ball icon (placement mode), then pick the point on the grid.
    The grid covers the large map only, so the point is on the map. With flag, the icon is clicked while Shift is
    held, which turns it into the flag, and the point is then placed with Shift held (see _finish)."""
    global _placing_flag
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("place %s: GSPro not in front; not started", "flag" if flag else "ball")
        return
    _placing_flag = flag
    if not _map_to_large(hwnd):
        return
    if flag:
        _hold_key("shift", True)
    try:
        click(*_point(client_rect(hwnd), BALL_ICON), f"place {_what()}: icon")
    finally:
        if flag:
            _hold_key("shift", False)
    start(on_final=_finish, region=_expanded_bounds())


def _cancel() -> None:
    """Close the grid, put the map back, and click the ball icon again, which backs out of placement mode."""
    stop()
    _map_restore()
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or not _force_foreground(hwnd):
        log.info("cancel grid: GSPro not in front; not clicked")
        return
    click(*_point(client_rect(hwnd), BALL_ICON), "cancel grid: ball icon")
    set_status("Grid cancelled")


def handle(event: tuple[str, int | None]) -> None:
    """Runs on the GUI thread. event is ("show", None), ("close", None), ("cancel", None), ("pick", index),
    or ("place", None). The index is the word's place in GRID_WORDS."""
    action, value = event
    if action == "show":
        start()
    elif action == "close":
        stop()
        _map_restore()
    elif action == "cancel":
        _cancel()
    elif action == "pick" and value is not None:
        pick(value)
    elif action == "redo":
        redo()
    elif action == "map":
        map_key()
    elif action == "place":
        _place_ball(flag=value == "flag")
