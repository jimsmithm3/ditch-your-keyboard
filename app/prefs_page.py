"""Preferences page: the MCT Constants table, ported to ditch-your-keyboard.

Layout comes from ui/preferences.ui (the MCT designer file, trimmed to the
Constants page). Each row is a PrefSpec. Edits go into a pending dict, and Save
writes them to ditch-your-keyboard.db through app.prefs. Calibration sits under the table
because it measures the room rather than editing a value.

Most settings are read when ditch-your-keyboard starts, so a saved change applies after a restart.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QFile, QIODevice, QSize, QSortFilterProxyModel, Qt
from PySide6.QtGui import QIcon, QStandardItem, QStandardItemModel
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.paths import resource_path
from app.prefs import get_pref, set_pref

HEADERS = ["Pref", "Descr", "Area", "Default", "Modified"]
MODIFIED_COL = 4
OFFSET_KEY = "spl_offset"
ORANGE = "background-color: #ff4500;"


@dataclass(frozen=True)
class PrefSpec:
    display: str  # "Pref" column
    key: str  # storage key in app.prefs
    descr: str  # "Descr" column
    area: str  # "Area" column
    default: str
    kind: str  # "TEXT" (typed box) or "DROPDOWN" (pick from options)
    subtype: str  # TEXT: NUMBER, FLOAT, EMAIL, URL, or "" for no check
    options: tuple[str, ...] = ()  # DROPDOWN choices


PREFS: list[PrefSpec] = [
    PrefSpec(
        "Baseline Room Noise",
        "baseline_room_db",
        "Quiet-room level in dB that Calibrate aims for",
        "MIC",
        "30",
        "TEXT",
        "NUMBER",
    ),
    PrefSpec(
        "Noise Gate",
        "noise_gate_db",
        "Input quieter than this (dBFS) is left out of Avg",
        "MIC",
        "-74",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Level Full Scale",
        "level_full_db",
        "Input level (dBFS) at which the level bar reads full",
        "MIC",
        "-30",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Calibrate Seconds",
        "calibrate_seconds",
        "How long Calibrate listens to the room",
        "MIC",
        "3",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Command Window",
        "command_window_seconds",
        "Seconds after the start phrase that a command is accepted",
        "VOICE",
        "5",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Wake Phrase Required",
        "wake_required",
        "On: say \"hey caddie\" before each command. Off: a command is heard on its own. Turn on for noisy rooms",
        "VOICE",
        "False",
        "DROPDOWN",
        "",
        ("True", "False"),
    ),
    PrefSpec(
        "Send Keys At Start",
        "send_keys_default",
        "Whether keys are sent to GSPro when ditch-your-keyboard starts",
        "VOICE",
        "True",
        "DROPDOWN",
        "",
        ("True", "False"),
    ),
    PrefSpec(
        "GSPro Settle Seconds",
        "gspro_settle_seconds",
        "Pause after a GSPro screen looks still, before the next click. Raise it on slower hardware",
        "GSPRO",
        "1.0",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "GSPro Short Settle Seconds",
        "gspro_settle_short_seconds",
        "Pause for screens that load quickly, such as round settings after Play",
        "GSPRO",
        "0.3",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Marker Stop Lag Seconds",
        "marker_stop_lag_seconds",
        "How far back the marker rewinds when you say stop, to cover the delay before stop is heard. 0 turns it off",
        "GSPRO",
        "1.0",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Slider Stop Lag Seconds",
        "slider_stop_lag_seconds",
        "How far back a range panel slider rewinds when you say stop, to cover the delay before stop is heard. 0 turns it off",
        "GSPRO",
        "1.0",
        "TEXT",
        "FLOAT",
    ),
    PrefSpec(
        "Confirm Exit",
        "confirm_exit",
        "On: say \"gspro exit\", then \"confirm exit\" within 8 seconds, to close GSPro and the connectors. Off (default): \"gspro exit\" closes them at once. Takes effect after a restart",
        "GSPRO",
        "False",
        "DROPDOWN",
        "",
        ("True", "False"),
    ),
    PrefSpec(
        "GSPro Overlay",
        "gspro_overlay",
        "On: the status line and last heard show over the bottom middle of the GSPro window. Off hides it. Takes effect right away",
        "GSPRO",
        "True",
        "DROPDOWN",
        "",
        ("True", "False"),
    ),
    PrefSpec(
        "Debug Mode",
        "debug_mode",
        "On: a box to the left of the status line lists the grammars listening right now. Takes effect right away",
        "GSPRO",
        "True",
        "DROPDOWN",
        "",
        ("True", "False"),
    ),
]
SPEC_BY_KEY = {spec.key: spec for spec in PREFS}
BASELINE = SPEC_BY_KEY["baseline_room_db"]


@dataclass(frozen=True)
class Tuning:
    gate_db: float
    full_scale_db: float
    calibrate_seconds: float
    command_window_seconds: float


def _setting(key: str) -> str:
    spec = SPEC_BY_KEY[key]
    return get_pref(key, spec.default)


def _float_setting(key: str) -> float:
    try:
        return float(_setting(key))
    except ValueError:
        return float(SPEC_BY_KEY[key].default)


def load_tuning() -> Tuning:
    """Timing and level values, read when the listener starts."""
    return Tuning(
        gate_db=_float_setting("noise_gate_db"),
        full_scale_db=_float_setting("level_full_db"),
        calibrate_seconds=_float_setting("calibrate_seconds"),
        command_window_seconds=_float_setting("command_window_seconds"),
    )


def send_keys_default() -> bool:
    return _setting("send_keys_default") == "True"


def validate(spec: PrefSpec, text: str) -> str | None:
    """Return an error message, or None when the text is acceptable."""
    if spec.kind == "DROPDOWN":
        return None if text in spec.options else f"[{spec.display}] must be one of {', '.join(spec.options)}"
    if spec.subtype == "NUMBER" and not re.fullmatch(r"\d+", text):
        return f"[{spec.display}] must be whole numbers only"
    if spec.subtype == "FLOAT" and not re.fullmatch(r"-?\d+(\.\d+)?", text):
        return f"[{spec.display}] must be a number"
    if spec.subtype == "EMAIL" and not re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text):
        return f"[{spec.display}] must be an email address"
    if spec.subtype == "URL" and not re.fullmatch(r"https?://\S+", text):
        return f"[{spec.display}] must start with http:// or https://"
    return None


def saved_offset() -> float:
    try:
        return float(get_pref(OFFSET_KEY, "0"))
    except ValueError:
        return 0.0


class _PrefFilter(QSortFilterProxyModel):
    """Text filter from the table's QSortFilterProxyModel, plus Hide Unchanged."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hide_unchanged = False

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if self.hide_unchanged:
            modified = self.sourceModel().index(source_row, MODIFIED_COL, source_parent).data()
            if not modified:
                return False
        return super().filterAcceptsRow(source_row, source_parent)


class PrefsPage(QWidget):
    def __init__(self, on_close: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._listener = None
        self._on_close = on_close
        self._pending: dict[str, str] = {}
        self._selected: PrefSpec | None = None

        ui_path = resource_path("ui", "preferences.ui")
        loader = QUiLoader()
        ui_file = QFile(str(ui_path))
        if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Cannot open {ui_path}: {ui_file.errorString()}")
        loaded = loader.load(ui_file)
        ui_file.close()
        if loaded is None:
            raise RuntimeError(f"Failed to load {ui_path}: {loader.errorString()}")
        self._ui = loaded
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(loaded)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        self._filter_text = self._find(QLineEdit, "ui_pref_filterLE")
        self._filter_column = self._find(QComboBox, "ui_pref_filterColumnDD")
        self._hide_unchanged = self._find(QCheckBox, "ui_pref_hideUnchangedTB")
        self._table = self._find(QTableView, "ui_pref_rtpTV")
        self._update_stack = self._find(QWidget, "ui_pref_updateSW")
        self._text_page = self._find(QWidget, "page_10")
        self._text_label = self._find(QLabel, "ui_pref_updateTextL")
        self._text_edit = self._find(QLineEdit, "ui_pref_updateTextLE")
        self._apply = self._find(QPushButton, "ui_pref_updateTextApplyPB")
        self._dropdown_page = self._find(QWidget, "ui_pref_updateDropDownP")
        self._dropdown_label = self._find(QLabel, "ui_pref_updateDropdownLL")
        self._dropdown = self._find(QComboBox, "ui_pref_updateDropdownDD")
        self._changes = self._find(QLabel, "ui_perfChangedL")
        self._save = self._find(QPushButton, "uiSaveB")
        self._cancel = self._find(QPushButton, "uiCancelB")
        self._status = self._find(QLabel, "uiStatusL")
        self._arrange()

        self._source = QStandardItemModel(0, len(HEADERS), self)
        self._source.setHorizontalHeaderLabels(HEADERS)
        self._proxy = _PrefFilter(self)
        self._proxy.setSourceModel(self._source)
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.selectionModel().selectionChanged.connect(self._on_select)

        self._filter_text.textChanged.connect(self._apply_filter)
        self._filter_column.currentIndexChanged.connect(self._apply_filter)
        self._hide_unchanged.toggled.connect(self._apply_filter)
        self._find(QPushButton, "ui_pref_filterClearPB").clicked.connect(self._clear_filter)
        self._apply.clicked.connect(self._on_apply)
        self._dropdown.currentIndexChanged.connect(self._on_dropdown_changed)
        self._save.clicked.connect(self._on_save)
        self._cancel.clicked.connect(self._on_cancel)

        self._fill()
        self._apply_filter()
        self._update_stack.setCurrentIndex(0)
        self._refresh_pending()

    def _arrange(self) -> None:
        """Replace the MCT fixed positions with real layouts so the page fits a small window."""

        def row(parent: QWidget, widgets: list, stretch_index: int | None = None, trailing_stretch=False):
            box = QHBoxLayout()
            box.setContentsMargins(6, 4, 6, 4)
            for index, widget in enumerate(widgets):
                box.addWidget(widget, 1 if index == stretch_index else 0)
            if trailing_stretch:
                box.addStretch(1)
            parent.setLayout(box)

        # Filter row: compact, Hide Unchanged on two lines, the text box takes the spare width.
        self._hide_unchanged.setText("Hide\nUnchanged")
        self._filter_column.setMaximumWidth(61)
        clear = self._find(QPushButton, "ui_pref_filterClearPB")
        clear.setText("")
        icon_path = resource_path("resources", "circle_x_48.png")
        clear.setIcon(QIcon(str(icon_path)) if icon_path.is_file() else self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        clear.setIconSize(QSize(16, 16))
        clear.setToolTip("Clear filter")
        clear.setMaximumWidth(30)
        row(
            self._find(QWidget, "groupBox_10"),
            [
                self._find(QLabel, "label_33"),
                self._filter_text,
                self._filter_column,
                self._hide_unchanged,
                clear,
            ],
            stretch_index=1,
        )

        # Update panel: a single row per type, with the edit box taking the spare width.
        box = QVBoxLayout()
        box.setContentsMargins(6, 4, 6, 4)
        box.addWidget(self._update_stack)
        self._find(QWidget, "groupBox_5").setLayout(box)
        row(self._text_page, [self._text_label, self._text_edit, self._apply], stretch_index=1)
        self._dropdown.setMaximumWidth(120)
        row(self._dropdown_page, [self._dropdown_label, self._dropdown], trailing_stretch=True)

        # Pending changes: label on the left, list of pending edits on the right.
        self._changes.setWordWrap(True)
        row(
            self._find(QWidget, "groupBox_3"),
            [self._find(QLabel, "label_34"), self._changes],
            stretch_index=1,
        )

    def _find(self, kind: type, name: str):
        widget = self._ui.findChild(kind, name)
        if widget is None:
            raise RuntimeError(f"preferences.ui is missing {name}")
        return widget

    # --- table -------------------------------------------------------------

    def _value(self, spec: PrefSpec) -> str:
        if spec.key in self._pending:
            return self._pending[spec.key]
        return get_pref(spec.key, spec.default)

    def _fill(self) -> None:
        self._source.setRowCount(0)
        for spec in PREFS:
            current = self._value(spec)
            modified = "" if current == spec.default else current
            cells = [spec.display, spec.descr, spec.area, spec.default, modified]
            items = []
            for text in cells:
                item = QStandardItem(text)
                item.setEditable(False)
                items.append(item)
            items[0].setData(spec.key, Qt.ItemDataRole.UserRole)
            self._source.appendRow(items)
        self._table.resizeColumnsToContents()

    def _select_key(self, key: str) -> None:
        for row in range(self._proxy.rowCount()):
            if self._proxy.index(row, 0).data(Qt.ItemDataRole.UserRole) == key:
                self._table.selectRow(row)
                return

    def _on_select(self, *_) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._selected = None
            self._update_stack.setCurrentIndex(0)
            return
        key = rows[0].data(Qt.ItemDataRole.UserRole)
        spec = SPEC_BY_KEY.get(key)
        if spec is None:
            return
        self._selected = spec
        value = self._value(spec)
        if spec.kind == "DROPDOWN":
            self._dropdown_label.setText(f"{spec.display}:")
            self._dropdown.blockSignals(True)
            self._dropdown.clear()
            self._dropdown.addItems(list(spec.options))
            self._dropdown.setCurrentText(value)
            self._dropdown.blockSignals(False)
            self._update_stack.setCurrentWidget(self._dropdown_page)
        else:
            self._update_stack.setCurrentWidget(self._text_page)
            self._text_label.setText(f"{spec.display}:")
            self._text_edit.setText(value)
            self._text_edit.setToolTip(spec.descr)

    def _apply_filter(self, *_) -> None:
        index = self._filter_column.currentIndex()
        self._proxy.setFilterKeyColumn(index - 1)  # 0 is "Any", which is -1 for all columns
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterFixedString(self._filter_text.text())
        self._proxy.hide_unchanged = self._hide_unchanged.isChecked()
        self._proxy.invalidateFilter()

    def _clear_filter(self) -> None:
        self._filter_text.setText("")
        self._filter_column.setCurrentIndex(0)
        self._apply_filter()

    # --- edits -------------------------------------------------------------

    def _stage(self, spec: PrefSpec, text: str) -> None:
        error = validate(spec, text)
        if error:
            self._set_status(error, error=True)
            return
        if text == self._value(spec):
            self._set_status(f"No change to {spec.display}")
            return
        self._pending[spec.key] = text
        self._refresh_pending()
        self._set_status(f"Pending: {spec.display} = {text}")

    def _on_apply(self) -> None:
        if self._selected is not None:
            self._stage(self._selected, self._text_edit.text().strip())

    def _on_dropdown_changed(self, *_) -> None:
        if self._selected is not None and self._selected.kind == "DROPDOWN":
            self._stage(self._selected, self._dropdown.currentText())

    def _on_save(self) -> None:
        if not self._pending:
            self._set_status("Nothing to save. Change a value and press Apply first.")
            return
        for key, value in self._pending.items():
            set_pref(key, value)
        self._pending.clear()
        self._refresh_pending()
        self._set_status("Saved. Most settings apply after you restart ditch-your-keyboard.")

    def _on_cancel(self) -> None:
        """Close the page. If there are unsaved changes, ask first."""
        if self._pending:
            answer = QMessageBox.question(
                self,
                "Preferences",
                "You have unsaved changes. Lose them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._pending.clear()
        self._refresh_pending()
        self._on_select()  # reload the edit box and dropdown from the saved values
        if self._on_close is not None:
            self._on_close()

    def _refresh_pending(self) -> None:
        selected = self._selected.key if self._selected else None
        self._fill()
        if selected:
            self._select_key(selected)
        if not self._pending:
            self._changes.setText("None")
            self._changes.setToolTip("")
            self._save.setStyleSheet("")
        else:
            names = [f"{SPEC_BY_KEY[key].display}={value}" for key, value in self._pending.items()]
            self._changes.setText(", ".join(names))
            self._changes.setToolTip("\n".join(names))
            self._save.setStyleSheet(ORANGE)

    def _set_status(self, text: str, error: bool = False) -> None:
        self._status.setText(text)
        self._status.setStyleSheet("color: red;" if error else "")

