"""The Analyze overlap tab on the commands dialog: pairs of voice commands that sound alike, so trouble can be seen
before it happens. The work runs on a background thread (the first run takes about a minute; later runs read the
saved scores). See app/word_overlap.py for how the scores are worked out.
"""

import itertools
import logging
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.commands import ROWS
from app.word_overlap import _connect, first_word_distance, phrase_distance

log = logging.getLogger(__name__)

SHOW_BELOW = 0.25  # pairs whose phrase score is above this are not listed: they sound different enough
_COLUMNS = ("Score", "First word", "Command", "Sounds like", "Note")


def _analyze() -> tuple[list, int]:
    """Every pair of phrases from different commands, scored. Returns (listed pairs, phrases compared)."""
    entries = [(phrase, index) for index, row in enumerate(ROWS) for phrase in row.phrases]
    con = _connect()
    try:
        listed = []
        for (a, row_a), (b, row_b) in itertools.combinations(entries, 2):
            if row_a == row_b:
                continue  # a command's own aliases are not a clash
            score, exact = phrase_distance(a, b, con)
            if score > SHOW_BELOW:
                continue
            first, first_exact = first_word_distance(a, b, con)
            listed.append((score, first, a, b, exact and first_exact))
    finally:
        con.close()
    listed.sort(key=lambda item: (item[0], item[1]))  # the closest sounds first (the score already weights the first word)
    return listed, len(entries)


class _OverlapPage(QWidget):
    ready = Signal(object, int)  # emitted from the worker thread; the slot runs on the GUI thread

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._status = QLabel("Working out how close the command words sound. This takes about a minute the first time.")
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self._table.horizontalHeader()
        for column in range(len(_COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._status)
        layout.addWidget(self._table)
        self.ready.connect(self._fill)

    def start(self) -> None:
        threading.Thread(target=self._work, daemon=True, name="ditch-your-keyboard-overlap").start()

    def _work(self) -> None:
        try:
            listed, count = _analyze()
        except Exception:  # the tab says what went wrong; the app keeps running
            log.exception("overlap analysis failed")
            self.ready.emit([], -1)
            return
        self.ready.emit(listed, count)

    def _fill(self, listed: list, count: int) -> None:
        if count < 0:
            self._status.setText("The overlap check failed. See the log.")
            return
        self._table.setRowCount(len(listed))
        for row, (score, first, a, b, exact) in enumerate(listed):
            notes = []
            if first == 0.0 and a.split()[0] != b.split()[0]:
                notes.append("first words sound the same")  # different first words, same sound: the recogniser cannot pick
            if not exact:
                notes.append("spelling only")
            cells = (f"{score:.2f}", f"{first:.2f}", a, b, ", ".join(notes))
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column < 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(row, column, item)
        self._table.resizeRowsToContents()
        self._status.setText(
            f"{len(listed)} pairs at or below {SHOW_BELOW:.2f} out of {count} phrases. "
            "Score: 0 is the same sound; the first word counts double. First word: how alike the first words sound."
        )


def build_overlap_page() -> QWidget:
    page = _OverlapPage()
    page.start()
    return page
