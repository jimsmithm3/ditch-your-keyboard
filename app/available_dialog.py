"""The commands dialog: two tabs, "Current grammar" (what is listening now) and "Always on".

Both tabs use the same four columns as the screen tables: Say, Also say, What it does, Wired up. The
dialog sits over the top left of the GSPro window. It is click-through and does not take focus, so it
never blocks a click the sequences make and GSPro keeps the keyboard. "open commands" opens it,
"close commands" closes it, and "show current grammar" / "show always on" switch the tab while it is open.
Look and feel are not final.
"""

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QAbstractScrollArea, QHeaderView, QLabel, QTabWidget, QTableWidget, QVBoxLayout, QWidget

from app.connector_ui import _rect, find_window
from app.gspro_screens import GLOBAL
from app.gspro_ui import GSPRO_TITLE
from app.screen_table_dialog import current_rows, fill_table, phrase_rows

REFRESH_MS = 500  # the tables follow the screen or panel while the dialog is open
OFFSET = (20, 80)  # logical pixels from the GSPro window's top left corner
WIDTH_SHARE = 0.45  # the dialog's width as a share of the GSPro window's width
HEADERS = ["Say", "Also say", "What it does", "Wired up"]
BACKGROUND = "rgba(48, 48, 48, 185)"  # the dialog's tint, dark grey; the last number is the opacity (0 clear, 255 solid)
CURRENT_TAB = 0
ALWAYS_TAB = 1

_window: QWidget | None = None
_tabs: QTabWidget | None = None
_title: QLabel | None = None
_now_table: QTableWidget | None = None
_global_table: QTableWidget | None = None
_timer: QTimer | None = None


def _table() -> QTableWidget:
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(HEADERS)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setWordWrap(True)
    # The dialog is click-through, so a scrollbar could not be used. Each table grows to show all its rows.
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    return table


def _enlarge_say(table: QTableWidget) -> None:
    """The Say column is what people read, so it gets twice the table's font size."""
    base = table.font()
    big = QFont(base)
    big.setPointSizeF(base.pointSizeF() * 2 if base.pointSizeF() > 0 else 18.0)
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None:
            item.setFont(big)
    table.resizeRowsToContents()


def _place() -> None:
    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None or _window is None:
        return
    left, top, right, _bottom = _rect(hwnd)  # physical pixels
    screen = QGuiApplication.screenAt(QPoint(left, top)) or QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() or 1.0
    x, y = left / ratio + OFFSET[0], top / ratio + OFFSET[1]
    width = (right - left) / ratio * WIDTH_SHARE
    _window.move(int(x), int(y))
    _window.setFixedWidth(int(width))


def _refresh() -> None:
    if _window is None:
        return
    title, rows = current_rows()
    _title.setText(f"<b>Listening now: {title}</b>")
    fill_table(_now_table, rows)
    _enlarge_say(_now_table)
    fill_table(_global_table, phrase_rows(GLOBAL, "always on"))
    _enlarge_say(_global_table)
    _place()
    _window.adjustSize()  # the height follows the rows, since nothing scrolls


def _build() -> None:
    global _window, _tabs, _title, _now_table, _global_table, _timer
    flags = (
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.WindowDoesNotAcceptFocus
        | Qt.WindowType.WindowTransparentForInput
    )
    _window = QWidget(None, flags)
    _window.setObjectName("commandsDialog")
    _window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    _window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # lets the background alpha show
    # Only the window paints the tinted background; the labels and tables are see-through so the alpha does not stack.
    _window.setStyleSheet(
        f"#commandsDialog {{ background: {BACKGROUND}; }}"
        " QWidget { color: #f2f2f2; }"
        " QLabel { padding: 6px; background: transparent; }"
        " QTabWidget::pane { background: transparent; border: none; }"
        " QTabBar::tab { background: rgba(60, 66, 80, 150); padding: 4px 10px; }"
        " QTableWidget { background: transparent; gridline-color: rgba(255, 255, 255, 40); }"
        " QTableView::item { background: transparent; }"
        " QHeaderView::section { background: rgba(40, 46, 58, 150); color: #f2f2f2; }"
    )
    layout = QVBoxLayout(_window)
    _tabs = QTabWidget()
    _title = QLabel()
    _now_table = _table()
    now_page = QWidget()
    now_layout = QVBoxLayout(now_page)
    now_layout.addWidget(_title)
    now_layout.addWidget(_now_table)
    _global_table = _table()
    always_page = QWidget()
    always_layout = QVBoxLayout(always_page)
    always_layout.addWidget(_global_table)
    _tabs.addTab(now_page, "Current grammar")
    _tabs.addTab(always_page, "Always on")
    layout.addWidget(_tabs)
    _timer = QTimer(_window)
    _timer.timeout.connect(_refresh)


def show_available(action: str) -> None:
    """Handle a commands dialog action: "open", "close", "current" or "always". Runs on the GUI thread."""
    if _window is None:
        _build()
    if action == "open":
        _refresh()
        _window.show()
        _timer.start(REFRESH_MS)
    elif action == "close":
        _timer.stop()
        _window.hide()
    elif action == "current":
        _tabs.setCurrentIndex(CURRENT_TAB)
    elif action == "always":
        _tabs.setCurrentIndex(ALWAYS_TAB)
