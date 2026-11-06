"""Load the Designer main window and wire the microphone."""

import logging

from PySide6.QtCore import QEvent, QFile, QIODevice, QObject
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QWidget,
)

from app.bag_dialog import edit_bag
from app.gspro_bag_dialog import edit_gspro_bag
from app.commands_dialog import show_commands
from app.listener import VoiceListener
from app.paths import resource_path
from app.player_dialog import choose_player

log = logging.getLogger(__name__)

_WAITING = "QMainWindow, QWidget#centralwidget { background-color: #d9f5d9; }"


class MainWindow:
    def __init__(self) -> None:
        ui_path = resource_path("ui", "main_window.ui")
        loader = QUiLoader()
        ui_file = QFile(str(ui_path))
        if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Cannot open {ui_path}: {ui_file.errorString()}")
        loaded = loader.load(ui_file)
        ui_file.close()
        if not isinstance(loaded, QMainWindow):
            raise RuntimeError(f"Failed to load {ui_path}: {loader.errorString()}")

        self.window = loaded
        self._notice = _status_bar(loaded)
        self._status = _require(self.window, QLabel, "statusLabel")
        self._heard = _require(self.window, QLabel, "heardLabel")
        self._command = _require(self.window, QLabel, "commandLabel")
        self._player = _require(self.window, QLabel, "playerLabel")
        self._bag = _require(self.window, QLabel, "bagLabel")
        self._club = _require(self.window, QLabel, "clubLabel")
        self._level = _require(self.window, QProgressBar, "levelBar")
        self._mic = _require(self.window, QComboBox, "micCombo")
        self._send_keys = _require(self.window, QCheckBox, "sendKeysCheck")
        self._edit_bag = _require(self.window, QPushButton, "editBagButton")
        self._gspro_bag = _require(self.window, QPushButton, "gsproBagButton")
        self._commands = _require(self.window, QPushButton, "commandsButton")
        self._change_player = _require(self.window, QPushButton, "changePlayerButton")

        self.player_id = choose_player(self.window)
        self.listener = None
        if self.player_id is None:
            return
        self._show_player()

        self.listener = VoiceListener()
        self._show_bag()
        self.listener.level.connect(self._level.setValue)
        self.listener.status.connect(self._on_status)
        self.listener.heard.connect(self._on_heard)
        self.listener.command.connect(self._on_command)
        self.listener.notice.connect(self._on_notice)
        self.listener.club.connect(self._on_club)
        self._on_club(self.listener.bag.club)
        self.listener.mics.connect(self._on_mics)
        self._send_keys.toggled.connect(self._on_send_keys)
        self.listener.send_keys = self._send_keys.isChecked()
        self._edit_bag.clicked.connect(self._on_edit_bag)
        self._gspro_bag.clicked.connect(lambda: edit_gspro_bag(self.window))
        self._commands.clicked.connect(self._on_commands)
        self._change_player.clicked.connect(self._on_change_player)
        self._mic.currentIndexChanged.connect(self._on_mic_changed)
        self._closer = _CloseFilter(self.listener, self.window)
        self.window.installEventFilter(self._closer)
        self.listener.start()
        log.info("loaded %s", ui_path)

    def show(self) -> None:
        if self.listener is None:
            self.window.close()
            return
        self.window.show()

    def _on_mics(self, payload: object) -> None:
        devices, preferred = payload
        self._mic.blockSignals(True)
        self._mic.clear()
        select = 0
        for row, (index, name) in enumerate(devices):
            self._mic.addItem(name, index)
            if index == preferred:
                select = row
        if devices:
            self._mic.setCurrentIndex(select)
        self._mic.blockSignals(False)
        if devices:
            self.listener.use_device(int(self._mic.currentData()))

    def _on_mic_changed(self) -> None:
        if self._mic.currentIndex() < 0:
            return
        device = self._mic.currentData()
        log.info("using mic %s", device)
        self.listener.use_device(int(device))

    def _show_player(self) -> None:
        from app.players import list_players

        name = next((item[1] for item in list_players() if item[0] == self.player_id), "—")
        self._player.setText(f"Player: {name}")

    def _show_bag(self) -> None:
        if self.listener is None:
            return
        self._bag.setText(f"Bag: {self.listener.bag.summary()}")

    def _on_change_player(self) -> None:
        if self.listener is None:
            return
        player_id = choose_player(self.window, pick=True)
        if player_id is None:
            return
        self.player_id = player_id
        self._show_player()
        self.listener.use_player()
        self._show_bag()
        self._on_club(self.listener.bag.club)

    def _on_commands(self) -> None:
        show_commands(self.window)

    def _on_edit_bag(self) -> None:
        if edit_bag(self.window, self.listener.bag):
            self._show_bag()
            self._on_club(self.listener.bag.club)
            log.info("bag saved: %s", ", ".join(self.listener.bag.enabled_names()))

    def _on_send_keys(self, checked: bool) -> None:
        self.listener.send_keys = checked
        log.info("send keys %s", checked)

    def _on_status(self, text: str) -> None:
        self._status.setText(text)
        waiting = text in ("Listening for a command", 'Say "hey caddy stop"')
        self.window.setStyleSheet(_WAITING if waiting else "")

    def _on_heard(self, text: str) -> None:
        self._heard.setText(f"Heard: {text}")

    def _on_command(self, text: str) -> None:
        self._command.setText(f"Command: {text}")

    def _on_notice(self, text: str) -> None:
        if text:
            self._notice.showMessage(text)
        else:
            self._notice.clearMessage()

    def _on_club(self, name: str) -> None:
        self._club.setText(f"Current club selected: {name}")


class _CloseFilter(QObject):
    def __init__(self, listener: VoiceListener, parent: QObject) -> None:
        super().__init__(parent)
        self._listener = listener

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            self._listener.shutdown()
        return False


def _status_bar(window: QMainWindow) -> QStatusBar:
    bar = window.findChild(QStatusBar, "statusbar")
    if bar is None:
        return window.statusBar()
    window.setStatusBar(bar)
    return bar


def _require(window: QWidget, kind: type, name: str):
    widget = window.findChild(kind, name)
    if widget is None:
        raise RuntimeError(f"main_window.ui is missing {name}")
    return widget
