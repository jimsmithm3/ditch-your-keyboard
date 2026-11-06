"""Table of GSPro commands. Unwired rows are light red."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QDialog, QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.commands import ROWS, key_text, voice_text

_UNWIRED = QBrush(QColor(255, 214, 214))
_COLUMNS = ("Area", "Keystroke", "Voice command", "Description", "Close", "Continue")


def show_commands(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Commands")
    dialog.resize(820, 480)
    layout = QVBoxLayout(dialog)

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
    header.setSectionsClickable(True)

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
    table.resizeRowsToContents()
    layout.addWidget(table)
    dialog.exec()
