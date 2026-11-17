"""Commands page: the table of GSPro voice commands. Unwired rows are light red.

The Tested column is saved in ditch-your-keyboard.db (via app.prefs), keyed by each row's
first phrase, so the list of what still needs testing survives restarts.
Click a Tested cell to toggle Yes / No.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.bag import spoken_phrases
from app.gspro_courses import course_phrases
from app.commands import ROWS, Command, key_text, primary, shown
from app.gspro_screens import (
    GLOBAL,
    GRID_GROUP,
    active_groups,
    group_phrases,
    GRID_PHRASES,
    GROUP_GRAMMAR_NAMES,
    PANEL_GROUP_NAMES,
    VIEW_GROUP_NAMES,
    SCREEN_GROUP_NAMES,
    overlay_phrases,
    SCREEN_RECORDS,
    grammar_name,
    panel_group,
    screen_group,
    screen_phrases,
)
from app.prefs import get_bool, set_bool
from app.screen_table_dialog import collapse_names, show_screen_table

_UNWIRED = QBrush(QColor(255, 214, 214))
_COLUMNS = ("Area", "Keystroke", "Voice command", "Description", "Close", "Continue", "Tested")
_TESTED = len(_COLUMNS) - 1
_KEY_ROLE = Qt.ItemDataRole.UserRole
_GROUP_ROLE = Qt.ItemDataRole.UserRole + 1  # the grammar group name on a grammar list item
_NARROW_COLUMNS = ("Always on", "Sync")  # the Active commands columns that are always the same; drag them wider if needed
_NARROW_WIDTH = 20  # pixels
_ROW_HEIGHT = 22  # pixels; one line per phrase


def _stroke(command: Command) -> str:
    keys = command.keys
    return keys if isinstance(keys, str) else "+".join(keys)


def _shared_strokes() -> set[str]:
    counts: dict[str, int] = {}
    for command in ROWS:
        stroke = _stroke(command)
        if stroke:
            counts[stroke] = counts.get(stroke, 0) + 1
    return {stroke for stroke, count in counts.items() if count > 1}


_SHARED = _shared_strokes()


def _test_key(command: Command) -> str:
    """Keystroke is the identity. Add the voice phrase when there is no keystroke
    (stop, close) or the keystroke is shared (left/right for aim and range finder)."""
    stroke = _stroke(command)
    if not stroke:
        return "tested.phrase:" + command.phrases[0]
    if stroke in _SHARED:
        return f"tested.key:{stroke}|{command.phrases[0]}"
    return f"tested.key:{stroke}"


def _voice_cell(command: Command) -> str:
    """Each alternate phrase on its own line in the cell, so the column stays narrow."""
    if command.hold and not command.repeat:
        return "\n".join(f"{phrase} (until stop)" for phrase in command.phrases)
    if not command.repeat:
        return "\n".join(command.phrases)
    return "\n".join(shown(phrase) for phrase in command.phrases)  # (#): a number can be said after it


def build_commands_page() -> QWidget:
    page = QWidget()
    page.setObjectName("commandsPage")
    layout = QVBoxLayout(page)

    screen_button = QPushButton("Screen table...")
    screen_button.clicked.connect(lambda: show_screen_table(page))
    layout.addWidget(screen_button)

    summary = QLabel()
    layout.addWidget(summary)

    table = QTableWidget(len(ROWS), len(_COLUMNS))
    table.setHorizontalHeaderLabels(list(_COLUMNS))
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setWordWrap(True)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(_TESTED, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionsClickable(True)

    def refresh_summary() -> None:
        wired = [r for r in ROWS if r.wired]
        done = sum(1 for r in wired if get_bool(_test_key(r), False))
        summary.setText(f"Tested: {done} of {len(wired)} wired commands. Click a Tested cell to toggle.")

    def set_tested_text(row: int, yes: bool) -> None:
        item = table.item(row, _TESTED)
        item.setText("Yes" if yes else "No")

    for row, command in enumerate(ROWS):
        values = (
            command.area,
            key_text(command.keys),
            _voice_cell(command),
            command.description,
            "Yes" if command.closes else "",
            "Yes" if command.repeat or command.hold else "",
        )
        for column, text in enumerate(values):
            item = QTableWidgetItem(text)
            if not command.wired:
                item.setBackground(_UNWIRED)
            table.setItem(row, column, item)
        key_item = table.item(row, 0)
        key_item.setData(_KEY_ROLE, _test_key(command))
        tested_item = QTableWidgetItem("Yes" if get_bool(_test_key(command), False) else "No")
        if not command.wired:
            tested_item.setBackground(_UNWIRED)
        table.setItem(row, _TESTED, tested_item)

    def toggle_tested(row: int, column: int) -> None:
        if column != _TESTED:
            return
        key = table.item(row, 0).data(_KEY_ROLE)
        yes = table.item(row, _TESTED).text() != "Yes"
        set_bool(key, yes)
        set_tested_text(row, yes)
        refresh_summary()

    sorted_column = -1

    def sort_column(index: int) -> None:
        nonlocal sorted_column
        ascending = header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        if sorted_column == index and ascending:
            order = Qt.SortOrder.DescendingOrder
        else:
            order = Qt.SortOrder.AscendingOrder
        sorted_column = index
        header.setSortIndicatorShown(True)
        header.setSortIndicator(index, order)
        table.sortItems(index, order)
        table.resizeRowsToContents()

    header.sectionClicked.connect(sort_column)
    table.cellClicked.connect(toggle_tested)
    table.resizeRowsToContents()
    refresh_summary()
    layout.addWidget(table)
    tabs = QTabWidget()
    tabs.addTab(page, "Commands")
    tabs.addTab(build_active_page(), "Active commands")
    return tabs


def _primaries(phrases) -> list[str]:
    """Each command once, by its primary name (aliases left out)."""
    names: list[str] = []
    for phrase in phrases:
        if primary(phrase) == phrase and shown(phrase) not in names:
            names.append(shown(phrase))
    return sorted(collapse_names(names), key=str.lower)  # alphabetical, so a phrase is easy to find


def _group_column(group: str, spoken) -> tuple[str, list[str]]:
    """One listening grammar: its readable name, then its commands by primary name."""
    if group.startswith("screen:"):
        return grammar_name(group), _primaries(screen_phrases(group[len("screen:"):]))
    if group.startswith(("panel:", "view:")):
        return grammar_name(group), _primaries(overlay_phrases(group.split(":", 1)[1]))
    if group.startswith("group:"):
        return grammar_name(group), _primaries(group_phrases(group[len("group:"):], spoken))
    if group == GRID_GROUP:
        return grammar_name(group), _primaries(GRID_PHRASES)
    if group == "courses":
        return grammar_name(group), _primaries(course_phrases())  # cached, so cheap to read on each refresh
    return grammar_name(group), []


def _active_columns() -> list[tuple[str, list[str]]]:
    """Always on, then each grammar listening right now. Only the active ones are shown."""
    spoken = tuple(spoken_phrases())
    columns: list[tuple[str, list[str]]] = [("Always on", _primaries(GLOBAL))]
    for group in active_groups():
        columns.append(_group_column(group, spoken))
    return columns


def _all_grammars() -> list[str]:
    """Every grammar the app can switch on, by group name."""
    return [*SCREEN_GROUP_NAMES, *PANEL_GROUP_NAMES, *VIEW_GROUP_NAMES, *GROUP_GRAMMAR_NAMES, GRID_GROUP]


def build_active_page() -> QWidget:
    """Left, three quarters: the grammars listening now, side by side. Right: the grammars not listening,
    and clicking one lists its phrases beside it, so it is easy to see what a page or panel is missing."""
    page = QWidget()
    layout = QHBoxLayout(page)
    table = QTableWidget(0, 0)
    table.setWordWrap(False)  # long text is cut off with an ellipsis, so narrow columns do not make tall rows
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)  # fixed rows; the table is not resized to fit text
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    layout.addWidget(table, stretch=3)
    idle = QListWidget()  # grammars not listening right now
    idle.setToolTip("Click a grammar to list its phrases")
    phrases = QListWidget()  # the phrases of the grammar clicked
    phrases.setSelectionMode(QListWidget.SelectionMode.NoSelection)
    layout.addWidget(idle, stretch=1)
    layout.addWidget(phrases, stretch=1)
    shown: list = [None]
    listed: list = [None]
    shown_phrases: list = [None]

    def refresh_table() -> None:
        columns = _active_columns()
        signature = tuple((name, tuple(names)) for name, names in columns)
        if signature == shown[0]:
            return  # nothing changed: leave the table alone
        shown[0] = signature
        table.clear()
        table.setRowCount(max((len(names) for _, names in columns), default=0))
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([name for name, _ in columns])
        for col, (_name, names) in enumerate(columns):
            for row, phrase in enumerate(names):
                table.setItem(row, col, QTableWidgetItem(phrase))
        table.resizeColumnsToContents()
        for col, (name, _names) in enumerate(columns):
            if name in _NARROW_COLUMNS:
                table.setColumnWidth(col, _NARROW_WIDTH)  # always on and sync are known: keep them narrow

    def refresh_idle() -> None:
        inactive = sorted(
            (group for group in _all_grammars() if group not in active_groups()),
            key=lambda group: grammar_name(group).lower(),  # alphabetical by the name shown
        )
        if inactive == listed[0]:
            return
        current = idle.currentItem().data(_GROUP_ROLE) if idle.currentItem() else None
        listed[0] = inactive
        idle.clear()
        for group in inactive:
            item = QListWidgetItem(grammar_name(group))
            item.setData(_GROUP_ROLE, group)
            idle.addItem(item)
            if group == current:
                idle.setCurrentItem(item)

    def refresh_phrases() -> None:
        item = idle.currentItem()
        names = [] if item is None else _group_column(item.data(_GROUP_ROLE), tuple(spoken_phrases()))[1]
        if names == shown_phrases[0]:
            return  # same list: leave it alone, so it keeps its scroll position
        shown_phrases[0] = names
        phrases.clear()
        phrases.addItems(names)

    def refresh() -> None:
        refresh_table()
        refresh_idle()
        refresh_phrases()

    idle.currentRowChanged.connect(lambda _row: refresh_phrases())
    refresh()
    timer = QTimer(page)  # follows the grammars while the tab is open
    timer.timeout.connect(refresh)
    timer.start(500)
    return page
