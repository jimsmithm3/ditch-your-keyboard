"""Left-nav shell: a list on the left switches a stacked set of pages.

The Designer central widget becomes the first page ("Voice") so the existing
.ui layout and findChild lookups keep working. Add a page with add_page().
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QStackedWidget,
    QWidget,
)

from app.commands_page import build_commands_page
from app.developer_page import build_developer_page
from app.hardware_page import build_hardware_page
from app.overview_page import OverviewPage
from app.paths import writable_dir

LOG_TAIL_LINES = 300


class Shell:
    def __init__(self, window: QMainWindow) -> None:
        self._window = window
        self._nav = QListWidget()
        self._nav.setFixedWidth(120)
        self._stack = QStackedWidget()

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._nav)
        layout.addWidget(self._stack, 1)
        window.setCentralWidget(root)

        self._watchers: list = []
        self._nav.currentRowChanged.connect(self._on_row)

    def _on_row(self, row: int) -> None:
        if row < 0:
            return
        self._stack.setCurrentIndex(row)
        title = self._nav.item(row).text()
        for callback in self._watchers:
            callback(title)

    def watch(self, callback) -> None:
        """callback(title) runs whenever a different page is shown."""
        self._watchers.append(callback)

    def current_title(self) -> str:
        item = self._nav.currentItem()
        return item.text() if item is not None else ""

    def add_page(self, title: str, page: QWidget) -> None:
        self._stack.addWidget(page)
        self._nav.addItem(title)
        if self._nav.count() == 1:
            self._nav.setCurrentRow(0)

    def insert_page(self, title: str, page: QWidget, index: int = 0) -> None:
        self._stack.insertWidget(index, page)
        self._nav.insertItem(index, title)

    def widget(self, title: str) -> QWidget | None:
        for row in range(self._nav.count()):
            if self._nav.item(row).text() == title:
                return self._stack.widget(row)
        return None

    def select(self, title: str) -> None:
        for row in range(self._nav.count()):
            if self._nav.item(row).text() == title:
                self._nav.setCurrentRow(row)
                return


def build_shell(window: QMainWindow, mic_page: QWidget, prefs_page: QWidget) -> Shell:
    voice_page = window.takeCentralWidget()  # detach first, or setCentralWidget deletes it
    shell = Shell(window)
    shell.add_page("Voice", voice_page)
    shell.add_page("Mic setup", mic_page)
    shell.add_page("Commands", build_commands_page())
    shell.add_page("Hardware", build_hardware_page())
    shell.add_page("Preferences", prefs_page)
    shell.add_page("Log", _log_page())
    shell.add_page("Developer", build_developer_page())
    # Overview is first in the list and opens first. It listens for voice commands like the Voice page.
    shell.insert_page("Overview", OverviewPage(), 0)
    shell.select("Overview")
    return shell


def _log_page() -> QWidget:
    view = QPlainTextEdit()
    view.setReadOnly(True)
    view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    log_file = writable_dir() / "logs" / "ditch-your-keyboard.log"

    def refresh() -> None:
        try:
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = ["(no log file yet)"]
        at_end = view.verticalScrollBar().value() >= view.verticalScrollBar().maximum() - 2
        view.setPlainText("\n".join(lines[-LOG_TAIL_LINES:]))
        if at_end:
            view.moveCursor(QTextCursor.MoveOperation.End)

    timer = QTimer(view)
    timer.timeout.connect(refresh)
    timer.start(1000)
    refresh()
    view.setObjectName("logPage")
    return view
