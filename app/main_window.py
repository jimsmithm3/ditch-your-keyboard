"""Load the Designer main window and wire the microphone."""

import logging

from PySide6.QtCore import QEvent, QFile, QIODevice, QObject, QTimer
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

from app import course_chooser
from app.bag_dialog import edit_bag
from app.gspro_settings import read_map_side
from app.listener import VoiceListener
from app.mic_page import MicSetupPage
from app.prefs_page import PrefsPage, saved_offset, send_keys_default
from app.paths import resource_path
from app.player_dialog import choose_player
from app.shell import build_shell

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
        self._edit_bag = _require(self.window, QPushButton, "editBagButton")
        self._change_player = _require(self.window, QPushButton, "changePlayerButton")
        self._mic_page = MicSetupPage(
            self._mic,
            _require(self.window, QLabel, "micCaption"),
            self._level,
        )
        self._prefs_page = PrefsPage(on_close=self._leave_prefs)
        self.shell = build_shell(self.window, self._mic_page, self._prefs_page)
        self.shell.watch(self._on_page)

        self.player_id = choose_player(self.window)
        self.listener = None
        if self.player_id is None:
            return
        self._show_player()

        read_map_side()  # once at startup: which side GSPro's mini map is on, for the grid
        self.listener = VoiceListener(spl_offset=saved_offset())
        course_chooser.on_download_done(self.listener.use_courses)
        self._mic_page.attach(self.listener)
        self.listener.use_page(self.shell.current_title())
        self.shell.widget("Overview").attach(self.listener)
        self._show_bag()
        self.listener.level.connect(self._level.setValue)
        self.listener.status.connect(self._on_status)
        self.listener.heard.connect(self._on_heard)
        self.listener.command.connect(self._on_command)
        self.listener.notice.connect(self._on_notice)
        self.listener.available.connect(self._on_available)
        self.listener.grid.connect(self._on_grid)
        self.listener.legend.connect(self._on_legend)
        self.listener.grammars.connect(self._on_grammars)
        self.listener.club.connect(self._on_club)
        self._on_club(self.listener.bag.club)
        self.listener.mics.connect(self._on_mics)
        # The send-keys switch lives on the Developer page. Keys go out by default.
        self._send_keys = self.shell.widget("Developer").send_keys_check
        self._send_keys.toggled.connect(self._on_send_keys)
        self.listener.send_keys = self._send_keys.isChecked()
        self._edit_bag.clicked.connect(self._on_edit_bag)
        self._change_player.clicked.connect(self._on_change_player)
        self._mic.currentIndexChanged.connect(self._on_mic_changed)
        self._closer = _CloseFilter(self.listener, self.window)
        self.window.installEventFilter(self._closer)
        # Status bar shows what a GSPro step is doing. The timer reads it, so no thread touches the bar.
        self._working_timer = QTimer(self.window)
        self._working_timer.timeout.connect(self._show_working)
        self._working_timer.start(300)
        self.listener.start()
        log.info("loaded %s", ui_path)

    def _leave_prefs(self) -> None:
        self.shell.select("Voice")

    def _on_page(self, title: str) -> None:
        if self.listener is not None:
            self.listener.use_page(title)

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
        name = self._mic.currentText()
        log.info("using mic %s (%s)", device, name)
        from app.prefs import set_pref

        set_pref("mic_name", name)
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

    def _on_edit_bag(self) -> None:
        if edit_bag(self.window, self.listener.bag):
            self._show_bag()
            self._on_club(self.listener.bag.club)
            log.info("bag saved: %s", ", ".join(self.listener.bag.enabled_names()))

    def _on_send_keys(self, checked: bool) -> None:
        self.listener.send_keys = checked
        log.info("send keys %s", checked)

    def _on_status(self, text: str) -> None:
        from app.gspro_overlay import set_status

        set_status(text)
        self._status.setText(text)
        waiting = text in ("Listening for a command", 'Say "hey caddy stop"')
        self.window.setStyleSheet(_WAITING if waiting else "")

    def _on_heard(self, text: str) -> None:
        from app.gspro_overlay import set_heard

        set_heard(text)
        self._heard.setText(f"Heard: {text}")

    def _on_command(self, text: str) -> None:
        self._command.setText(f"Command: {text}")

    def _show_working(self) -> None:
        from app.progress import current

        text = current()
        if text:
            self._notice.showMessage(f"Working: {text}")
        elif self._notice.currentMessage().startswith("Working:"):
            self._notice.clearMessage()  # leave a finished result message in place

    def _on_grammars(self, names: object) -> None:
        from app.gspro_overlay import set_grammars

        set_grammars(list(names))

    def _on_grid(self, event: object) -> None:
        from app.gspro_grid import handle

        handle(event)

    def _on_legend(self, state: object) -> None:
        from app.gspro_legend import apply

        apply(state)

    def _on_available(self, action: str) -> None:
        from app.available_dialog import show_available

        show_available(action)

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
