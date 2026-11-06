"""Pick a GSPro locker bag and edit each club's shortcut name."""

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gspro_bag import GsproBag, club_names, load_bags, save_nicknames, yards

_COLUMNS = ("Club", "Yards", "Shortcut")


def edit_gspro_bag(parent: QWidget) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("GSPro bag")
    dialog.resize(480, 460)
    layout = QVBoxLayout(dialog)

    names = club_names()
    bags: list[GsproBag] = []
    message = QLabel("")
    message.setWordWrap(True)
    try:
        bags = load_bags()
    except FileNotFoundError:
        message.setText("GSPro bag file was not found.")
    except sqlite3.Error as exc:
        message.setText(f"Could not read the GSPro bag. {exc}")

    picker = QComboBox()
    for bag in bags:
        picker.addItem(bag.name or f"Bag {bag.id}", bag.id)
    layout.addWidget(picker)

    table = QTableWidget(0, len(_COLUMNS))
    table.setHorizontalHeaderLabels(list(_COLUMNS))
    table.verticalHeader().setVisible(False)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    layout.addWidget(table)
    layout.addWidget(message)

    row = QHBoxLayout()
    save = QPushButton("Save")
    cancel = QPushButton("Cancel")
    save.setEnabled(bool(bags))
    row.addWidget(save)
    row.addWidget(cancel)
    layout.addLayout(row)

    def show_bag() -> None:
        bag_id = picker.currentData()
        bag = next((item for item in bags if item.id == bag_id), None)
        table.setRowCount(0 if bag is None else len(bag.clubs))
        if bag is None:
            return
        for index, club in enumerate(bag.clubs):
            catalog = names.get(int(club.get("GSProClubIndex", -1)), "Unknown")
            _cell(table, index, 0, catalog, editable=False)
            _cell(table, index, 1, yards(club.get("AverageDistance", 0)), editable=False)
            _cell(table, index, 2, str(club.get("ClubNickName") or ""), editable=True)

    def on_save() -> None:
        bag_id = picker.currentData()
        nicknames = [table.item(index, 2).text().strip() for index in range(table.rowCount())]
        try:
            save_nicknames(int(bag_id), nicknames)
        except Exception as exc:
            message.setText(f"Could not save. {exc}")
            return
        dialog.accept()

    picker.currentIndexChanged.connect(show_bag)
    show_bag()
    save.clicked.connect(on_save)
    cancel.clicked.connect(dialog.reject)
    dialog.exec()


def _cell(table: QTableWidget, row: int, column: int, text: str, *, editable: bool) -> None:
    item = QTableWidgetItem(text)
    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    if editable:
        flags |= Qt.ItemFlag.ItemIsEditable
    item.setFlags(flags)
    table.setItem(row, column, item)
