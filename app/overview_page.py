"""Overview page: a glanceable "is it alive" view for the floor display (OBS).

Shows three green/red circles and the last command heard. The circles are
read from the connector window and the process list, so they reflect what
the apps report, not what this app assumes.
"""

import logging
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.connector_ui import lights
from app.launch import _process_running

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

    def _on_command(self, text: str) -> None:
        self._last_command.setText(f"Last command: {text}  ({datetime.now().strftime('%H:%M:%S')})")

    def _on_heard(self, text: str) -> None:
        self._last_heard.setText(f"Last heard: {text}")
