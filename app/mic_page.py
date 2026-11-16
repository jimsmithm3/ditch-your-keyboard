"""Mic setup page: microphone chooser, input level, recognizer choice, and a live transcript table.

Words are captured only while this page is open. Voice commands are processed
only while the Voice page is open. The page switch is handled in shell.py and
main_window.py, which call listener.use_page().
"""

import math
import time
from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.prefs import get_pref, set_pref
from app.prefs_page import OFFSET_KEY, saved_offset

BASELINE_KEY = "baseline_room_db"
TRANSCRIPT_ROWS = 2000  # a running log for research, so it is kept long
COLUMNS = ["When", "Page", "Heard", "Action", "Avg dB", "Peak dB"]
WHEN_COL, PAGE_COL, HEARD_COL, ACTION_COL, AVG_COL, PEAK_COL = range(6)
SMOOTH_SECONDS = 0.5  # the level label averages this long; the bar is not smoothed


def _db_text(value: float) -> str:
    """Calibrated dB, the same format as a sound meter."""
    return f"{value:.0f} dB"


class MicSetupPage(QWidget):
    def __init__(self, mic_combo: QComboBox, mic_caption: QLabel, level_bar: QProgressBar) -> None:
        super().__init__()
        self._recent: deque = deque()  # (time, dB) for the smoothed label

        # Move the chooser and level bar out of the Voice page's layout into this page.
        for widget in (mic_caption, mic_combo, level_bar):
            parent = widget.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().removeWidget(widget)

        self._db = QLabel("— dB")
        self._db.setMinimumWidth(70)
        level_row = QHBoxLayout()
        level_row.addWidget(level_bar, 1)
        level_row.addWidget(self._db)

        recognizer = QGroupBox("Recognizer")
        self._recognizer_note = QLabel(
            "Windows speech listens on the Windows default recording device, not the mic chosen above. "
            "Set that device in Windows Sound settings to your mic. The chooser above still drives the level meter."
        )
        self._recognizer_note.setWordWrap(True)
        QVBoxLayout(recognizer).addWidget(self._recognizer_note)

        self._note = QLabel(
            "Capture audio: shows words the command grammar knows. Speech it can't "
            "match shows as unknown. Open this page to capture."
        )
        self._note.setWordWrap(True)
        clear = QPushButton("Clear")
        copy = QPushButton("Copy")
        copy.setToolTip("Copy the selected rows, or all rows if none are selected (Ctrl+C also works)")
        clear_row = QHBoxLayout()
        clear_row.addWidget(self._note, 1)
        clear_row.addWidget(copy)
        clear_row.addWidget(clear)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        for column in range(len(COLUMNS)):
            mode = QHeaderView.ResizeMode.Stretch if column == HEARD_COL else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)
        clear.clicked.connect(lambda: self._table.setRowCount(0))
        copy.clicked.connect(self._copy_rows)
        QShortcut(QKeySequence.StandardKey.Copy, self._table, activated=self._copy_rows)

        # Calibration tunes this page's readout, so it lives here rather than in Preferences.
        self._listener = None
        self._calibrate = QPushButton("Calibrate room noise")
        self._calibrate.setEnabled(False)
        self._calibrate.setToolTip("Be quiet for a few seconds, then press Calibrate")
        self._calibrate.clicked.connect(self._on_calibrate)
        self._offset = QLabel()
        self._offset.setWordWrap(True)
        self._cal_status = QLabel("")
        self._cal_status.setWordWrap(True)
        cal_row = QHBoxLayout()
        cal_row.addWidget(self._calibrate)
        cal_row.addWidget(self._offset, 1)
        self._show_offset(saved_offset())

        layout = QVBoxLayout(self)
        layout.addWidget(mic_caption)
        layout.addWidget(mic_combo)
        layout.addLayout(level_row)
        layout.addLayout(cal_row)
        layout.addWidget(self._cal_status)
        layout.addWidget(recognizer)
        layout.addLayout(clear_row)
        layout.addWidget(self._table, 1)

    def attach(self, listener) -> None:
        self._listener = listener
        listener.transcript.connect(self._on_said)
        listener.utterance.connect(self._on_voice_heard)
        listener.command.connect(self._on_voice_command)
        listener.decibels.connect(self._on_db)
        listener.calibrated.connect(self._on_calibrated)
        listener.status.connect(self._on_listener_status)
        self._calibrate.setEnabled(True)

    def _on_calibrate(self) -> None:
        if self._listener is None:
            return
        try:
            baseline = float(get_pref(BASELINE_KEY, "30"))
        except ValueError:
            self._cal_status.setText("Baseline room noise in Preferences must be a number")
            return
        self._cal_status.setText("Calibrating. Stay quiet while it listens…")
        self._listener.calibrate(baseline)

    def _on_calibrated(self, offset: float) -> None:
        set_pref(OFFSET_KEY, f"{offset:.2f}")
        self._show_offset(offset)

    def _on_listener_status(self, text: str) -> None:
        if text.startswith("Calibrated") or text.startswith("No audio"):
            self._cal_status.setText(text)

    def _show_offset(self, offset: float) -> None:
        if offset == 0:
            self._offset.setText("Not calibrated. Readings are in dBFS (relative to full scale).")
        else:
            self._offset.setText(f"Offset {offset:+.1f} dB added to the mic's own level.")

    def _on_db(self, db: float) -> None:
        """Label only: the mean of the last half second, so the number holds still enough to read."""
        if math.isnan(db):
            self._recent.clear()
            self._db.setText("silent")
            return
        now = time.monotonic()
        self._recent.append((now, db))
        while self._recent and now - self._recent[0][0] > SMOOTH_SECONDS:
            self._recent.popleft()
        mean = sum(level for _, level in self._recent) / len(self._recent)
        self._db.setText(_db_text(mean))

    def _copy_rows(self) -> None:
        """Copy selected rows (or all rows) as tab-separated text, header first, so it pastes into a spreadsheet."""
        rows = sorted({index.row() for index in self._table.selectionModel().selectedRows()})
        if not rows:
            rows = list(range(self._table.rowCount()))
        if not rows:
            return
        lines = ["\t".join(COLUMNS)]
        for row in rows:
            cells = []
            for column in range(self._table.columnCount()):
                item = self._table.item(row, column)
                cells.append(item.text() if item is not None else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))

    def _on_said(self, text: str, avg_db: float, peak_db: float) -> None:
        """Mic setup capture: one row per phrase the capture recognizer heard."""
        self._add_row("Mic setup", text, "", avg_db, peak_db)

    def _on_voice_heard(self, text: str) -> None:
        """Voice page: each finished phrase gets a row. The dB columns are left blank."""
        self._add_row("Voice", text, "", float("nan"), float("nan"))

    def _on_voice_command(self, text: str) -> None:
        """The command result goes on the row of the phrase that caused it, which is the newest Voice row."""
        if self._table.rowCount() == 0 or self._table.item(0, PAGE_COL).text() != "Voice":
            return
        self._table.setItem(0, ACTION_COL, QTableWidgetItem(text))

    def _add_row(self, page: str, heard: str, action: str, avg_db: float, peak_db: float) -> None:
        """Newest row goes on top, so the latest line is always visible without scrolling."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._table.insertRow(0)
        self._table.setItem(0, WHEN_COL, QTableWidgetItem(now))
        self._table.setItem(0, PAGE_COL, QTableWidgetItem(page))
        self._table.setItem(0, HEARD_COL, QTableWidgetItem(heard))
        self._table.setItem(0, ACTION_COL, QTableWidgetItem(action))
        for column, value in ((AVG_COL, avg_db), (PEAK_COL, peak_db)):
            label = "—" if math.isnan(value) else _db_text(value)
            item = QTableWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(0, column, item)
        while self._table.rowCount() > TRANSCRIPT_ROWS:
            self._table.removeRow(self._table.rowCount() - 1)
