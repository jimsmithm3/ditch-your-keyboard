"""Mic setup page: microphone chooser, input level, recognizer choice, and a live transcript table.

Words are captured only while this page is open. Voice commands are processed
only while the Voice page is open. The page switch is handled in shell.py and
main_window.py, which call listener.use_page().
"""

import math
import time
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.prefs import get_pref, set_pref
from app.prefs_page import OFFSET_KEY, saved_offset

BASELINE_KEY = "baseline_room_db"
TRANSCRIPT_ROWS = 200
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
        self._vosk = QRadioButton("Vosk (offline, in use now)")
        self._vosk.setChecked(True)
        self._wsapi = QRadioButton("Windows speech API (WSAPI), not built yet")
        self._wsapi.setEnabled(False)
        self._wsapi.setToolTip("Not built yet. Vosk stays active.")
        group_layout = QVBoxLayout(recognizer)
        group_layout.addWidget(self._vosk)
        group_layout.addWidget(self._wsapi)

        self._note = QLabel(
            "Capture audio: shows words the command grammar knows. Speech it can't "
            "match shows as unknown. Open this page to capture."
        )
        self._note.setWordWrap(True)
        clear = QPushButton("Clear")
        clear_row = QHBoxLayout()
        clear_row.addWidget(self._note, 1)
        clear_row.addWidget(clear)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Heard", "Avg dB", "Peak dB"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        clear.clicked.connect(lambda: self._table.setRowCount(0))

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

    def _on_said(self, text: str, avg_db: float, peak_db: float) -> None:
        """Newest row goes on top, so the latest line is always visible without scrolling."""
        self._table.insertRow(0)
        self._table.setItem(0, 0, QTableWidgetItem(text))
        for column, value in ((1, avg_db), (2, peak_db)):
            label = "—" if math.isnan(value) else _db_text(value)
            item = QTableWidgetItem(label)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(0, column, item)
        while self._table.rowCount() > TRANSCRIPT_ROWS:
            self._table.removeRow(self._table.rowCount() - 1)
