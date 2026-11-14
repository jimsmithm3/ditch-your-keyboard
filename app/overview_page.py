"""Overview page: a glanceable "is it alive" view for the floor display (OBS).

Shows three green/red circles and the last command heard. The circles are
read from the connector window and the process list, so they reflect what
the apps report, not what this app assumes.
"""

import logging
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app import gspro_tree as tree
from app.connector_ui import lights
from app.gspro_sequences import CLOSED, current_screen
from app.launch import _process_running
from app.screen_table_dialog import show_screen_table

log = logging.getLogger(__name__)

POLL_MS = 5000
GREEN = "#2e7d32"
RED = "#c62828"
GRAY = "#777777"


def _collect() -> dict:
    """Runs on a worker thread. Reads the lights and checks the connector process."""
    light = lights()  # None when the connector window is not open
    return {
        "lm": bool(light and light["lm"]),
        "gspro": bool(light and light["gspro"]),
        "connector": _process_running("SQG-GSPRO-Connect.exe"),
        "checked": datetime.now().strftime("%H:%M:%S"),
    }


def _dot(color: str) -> str:
    return f"background-color: {color}; border-radius: 14px;"


class OverviewPage(QWidget):
    _status = Signal(object)  # emitted from the worker thread, delivered on the GUI thread

    CHECKS = (
        ("lm", "Launch monitor connected"),
        ("gspro", "GSPro connected"),
        ("connector", "Connector app running"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("overviewPage")
        self._busy = False

        layout = QVBoxLayout(self)
        self._dots: dict[str, QLabel] = {}
        for key, text in self.CHECKS:
            row = QHBoxLayout()
            dot = QLabel()
            dot.setFixedSize(28, 28)
            dot.setStyleSheet(_dot(GRAY))
            label = QLabel(text)
            row.addWidget(dot)
            row.addWidget(label, 1)
            layout.addLayout(row)
            self._dots[key] = dot

        self._screen_title = QLabel("Screen: —")
        self._screen_rows = QVBoxLayout()
        layout.addSpacing(12)
        layout.addWidget(self._screen_title)
        layout.addLayout(self._screen_rows)
        commands_button = QPushButton("Commands...")  # opens the screen table window
        commands_button.clicked.connect(lambda: show_screen_table(None))
        layout.addWidget(commands_button)

        self._mode = QLabel("Voice: listening")
        self._mode.setStyleSheet("font-size: 22px; font-weight: bold; color: #2e7d32;")
        layout.addWidget(self._mode)
        self._working = QLabel("")
        self._working.setStyleSheet("font-size: 18px; color: #1565c0;")
        layout.addWidget(self._working)
        self._working_timer = QTimer(self)
        self._working_timer.timeout.connect(self._show_working)
        self._working_timer.start(300)

        self._last_command = QLabel("Last command: —")
        self._last_heard = QLabel("Last heard: —")
        self._checked = QLabel("")
        layout.addSpacing(12)
        layout.addWidget(self._last_command)
        layout.addWidget(self._last_heard)
        layout.addStretch(1)
        layout.addWidget(self._checked)

        self._status.connect(self._show)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_MS)
        self._poll()

    def attach(self, listener) -> None:
        listener.command.connect(self._on_command)
        listener.utterance.connect(self._on_heard)
        listener.mode.connect(self._on_mode)

    def _on_mode(self, on: bool) -> None:
        self._mode.setText("Voice: listening" if on else "Voice: PAUSED. Say toggle listening.")
        self._mode.setStyleSheet("font-size: 22px; font-weight: bold; color: " + ("#2e7d32;" if on else "#c62828;"))

    def _poll(self) -> None:
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=lambda: self._status.emit(_collect()), daemon=True).start()

    def _show(self, status: dict) -> None:
        self._busy = False
        for key, _ in self.CHECKS:
            self._dots[key].setStyleSheet(_dot(GREEN if status.get(key) else RED))
        self._checked.setText(f"Checked {status.get('checked', '?')}")
        self._render_screen()

    def _show_working(self) -> None:
        from app.progress import current

        text = current()
        self._working.setText(f"Working: {text}" if text else "")

    def _render_screen(self) -> None:
        while self._screen_rows.count():
            item = self._screen_rows.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if current_screen() == CLOSED:
            self._screen_title.setText("GSPro is not running. Say \"gspro start\".")
            self._screen_title.setStyleSheet("font-size: 26px; font-weight: bold;")
            return
        current = tree.screen(current_screen())
        if current is None:
            self._screen_title.setText("Screen: unknown (say a command to set it)")
            return
        self._screen_title.setText(f"Screen (last known): {current.name}")
        self._screen_title.setStyleSheet("font-size: 26px; font-weight: bold;")

    def _add_row(self, text: str, status: str, note: str = "") -> None:
        label = QLabel(f"{text}   ·   {status}" + (f"   ({note})" if note else ""))
        label.setStyleSheet("font-size: 20px; padding: 4px 0;")
        self._screen_rows.addWidget(label)

    def _on_command(self, text: str) -> None:
        self._last_command.setText(f"Last command: {text}  ({datetime.now().strftime('%H:%M:%S')})")
        self._render_screen()

    def _on_heard(self, text: str) -> None:
        # Count the same phrase said again in a row, so "close commands x2" shows two were heard.
        if text == getattr(self, "_heard_text", None):
            self._heard_count = getattr(self, "_heard_count", 1) + 1
        else:
            self._heard_text = text
            self._heard_count = 1
        suffix = f"  x{self._heard_count}" if self._heard_count > 1 else ""
        self._last_heard.setText(f"Last heard: {text}{suffix}")
