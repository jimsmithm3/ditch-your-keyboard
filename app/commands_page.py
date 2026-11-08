"""Commands page: the table of GSPro voice commands. Unwired rows are light red.

The Tested column is saved in gspraudio.db (via app.prefs), keyed by each row's
first phrase, so the list of what still needs testing survives restarts.
Click a Tested cell to toggle Yes / No.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.commands import ROWS, Command, key_text, voice_text
from app.prefs import get_bool, set_bool

_UNWIRED = QBrush(QColor(255, 214, 214))
_COLUMNS = ("Area", "Keystroke", "Voice command", "Description", "Close", "Continue", "Tested")
_TESTED = len(_COLUMNS) - 1
_KEY_ROLE = Qt.ItemDataRole.UserRole


def _stroke(command: Command) -> str:
    keys = command.keys
    return keys if isinstance(keys, str) else "+".join(keys)


def _shared_strokes() -> set[str]:
    counts: dict[str, int] = {}
    for command in ROWS:
        stroke = _stroke(command)
        if stroke:
            counts[stroke] = counts.get(stroke, 0) + 1
    return {stroke for stroke, count in counts.items() if count > 1}


_SHARED = _shared_strokes()


def _test_key(command: Command) -> str:
    """Keystroke is the identity. Add the voice phrase when there is no keystroke
    (stop, close) or the keystroke is shared (k for club down and reset club,
    left/right for aim and range finder)."""
    stroke = _stroke(command)
    if not stroke:
        return "tested.phrase:" + command.phrases[0]
    if stroke in _SHARED:
        return f"tested.key:{stroke}|{command.phrases[0]}"
    return f"tested.key:{stroke}"


def build_commands_page() -> QWidget:
    page = QWidget()
    page.setObjectName("commandsPage")
    layout = QVBoxLayout(page)

    summary = QLabel()
    layout.addWidget(summary)

    table = QTableWidget(len(ROWS), len(_COLUMNS))
    table.setHorizontalHeaderLabels(list(_COLUMNS))
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setWordWrap(True)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(_TESTED, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionsClickable(True)

    def refresh_summary() -> None:
        wired = [r for r in ROWS if r.wired]
        done = sum(1 for r in wired if get_bool(_test_key(r), False))
        summary.setText(f"Tested: {done} of {len(wired)} wired commands. Click a Tested cell to toggle.")

    def set_tested_text(row: int, yes: bool) -> None:
        item = table.item(row, _TESTED)
        item.setText("Yes" if yes else "No")

    for row, command in enumerate(ROWS):
        values = (
            command.area,
            key_text(command.keys),
            voice_text(command),
            command.description,
            "Yes" if command.closes else "",
            "Yes" if command.repeat or command.hold else "",
        )
        for column, text in enumerate(values):
            item = QTableWidgetItem(text)
            if not command.wired:
                item.setBackground(_UNWIRED)
            table.setItem(row, column, item)
        key_item = table.item(row, 0)
        key_item.setData(_KEY_ROLE, _test_key(command))
        tested_item = QTableWidgetItem("Yes" if get_bool(_test_key(command), False) else "No")
        if not command.wired:
            tested_item.setBackground(_UNWIRED)
        table.setItem(row, _TESTED, tested_item)

    def toggle_tested(row: int, column: int) -> None:
        if column != _TESTED:
            return
        key = table.item(row, 0).data(_KEY_ROLE)
        yes = table.item(row, _TESTED).text() != "Yes"
        set_bool(key, yes)
        set_tested_text(row, yes)
        refresh_summary()

    sorted_column = -1

    def sort_column(index: int) -> None:
        nonlocal sorted_column
        ascending = header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        if sorted_column == index and ascending:
            order = Qt.SortOrder.DescendingOrder
        else:
            order = Qt.SortOrder.AscendingOrder
        sorted_column = index
        header.setSortIndicatorShown(True)
        header.setSortIndicator(index, order)
        table.sortItems(index, order)
        table.resizeRowsToContents()

    header.sectionClicked.connect(sort_column)
    table.cellClicked.connect(toggle_tested)
    table.resizeRowsToContents()
    refresh_summary()
    layout.addWidget(table)
    return page
