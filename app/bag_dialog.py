"""Checkbox dialog for which catalog clubs are in the bag."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.bag import CATALOG, Bag

_GROUPS = ("woods", "irons", "wedges", "other")
_OVER_LIMIT = "background-color: #c0392b; color: white; padding: 4px;"
_UNDER_LIMIT = "padding: 4px;"


def edit_bag(parent: QWidget, bag: Bag) -> bool:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Edit bag")
    layout = QVBoxLayout(dialog)

    columns = QHBoxLayout()
    enabled = set(bag.enabled_names())
    checks: list[QCheckBox] = []
    for group in _GROUPS:
        column = QVBoxLayout()
        title = QLabel(group.capitalize())
        column.addWidget(title)
        for club in CATALOG:
            if club.group != group:
                continue
            box = QCheckBox(club.name)
            box.setChecked(club.name in enabled)
            column.addWidget(box)
            checks.append(box)
        column.addStretch(1)
        columns.addLayout(column)
    layout.addLayout(columns)

    count = QLabel("")
    layout.addWidget(count)
    message = QLabel("")
    message.setWordWrap(True)
    layout.addWidget(message)

    row = QHBoxLayout()
    save = QPushButton("Save")
    cancel = QPushButton("Cancel")
    row.addWidget(save)
    row.addWidget(cancel)
    layout.addLayout(row)

    def refresh_count() -> None:
        selected = sum(box.isChecked() for box in checks)
        count.setText(f"{selected} clubs")
        count.setStyleSheet(_OVER_LIMIT if selected > 14 else _UNDER_LIMIT)

    for box in checks:
        box.toggled.connect(refresh_count)
    refresh_count()

    saved = False

    def on_save() -> None:
        nonlocal saved
        names = [box.text() for box in checks if box.isChecked()]
        if not bag.set_enabled(names):
            message.setText("Pick at least one club.")
            return
        saved = True
        dialog.accept()

    save.clicked.connect(on_save)
    cancel.clicked.connect(dialog.reject)
    dialog.exec()
    return saved
