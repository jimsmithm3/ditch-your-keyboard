"""Screen table window, with two tabs: a table of screens by group, and a tree diagram.

Read-only for now. Table: one row per screen, one column per group; each cell lists the phrases
that group holds on that screen. Tree: a top-down diagram with Home at the top, its children
joined under it, and their children under those. Click a node to list every command that screen
can handle.

Rows, groups and the tree come from gspro_screens.py; the check at the bottom compares them
with the tree and commands.
"""

import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.commands import DIGIT_KEYS, ROWS, aliases_of, primary, shown
from app.gspro_sequences import current_panel, current_screen, current_view
from app.window_places import COMMANDS_KEY, remember, restore
from app.gspro_screens import (
    GLOBAL,
    recognizer_setup,
    GROUPS,
    PANEL_PARENTS,
    PANELS,
    VIEW_PARENTS,
    VIEWS,
    overlay_name,
    overlay_phrases,
    RECORDS_BY_KEY,
    SCREEN_RECORDS,
    check,
    label,
)

# What each command does, from its row in commands.py, so the descriptions match the app.
_DESCRIPTIONS: dict[str, str] = {phrase: row.description for row in ROWS for phrase in row.phrases}
_WIRED: dict[str, bool] = {phrase: row.wired for row in ROWS for phrase in row.phrases}
_NOT_WIRED = QBrush(QColor(255, 214, 214))  # same light red as the Commands page

_HAS = QBrush(QColor(214, 240, 214))  # the screen has this group
_NAMES = {screen.key: screen.name for screen in SCREEN_RECORDS}
ROOT = SCREEN_RECORDS[0]  # home: the one screen with no parent

FOLLOW_MS = 500  # how often the Tree checks whether GSPro moved to another screen
NODE_W, NODE_H = 170, 60  # a node box, in pixels; tall enough for a second line
LEAF_GAP = 190  # across, between leaves
LEVEL_GAP = 120  # down, between levels
_BRANCH_STYLE = "QPushButton { background: #9e9e9e; color: white; border-radius: 16px; font-weight: bold; }"
_LEAF_STYLE = "QPushButton { background: #7cb342; color: white; border-radius: 6px; font-weight: bold; }"
_PANEL_STYLE = "QPushButton { background: #1e88e5; color: white; border-radius: 6px; font-weight: bold; }"
_VIEW_STYLE = "QPushButton { background: #8e24aa; color: white; border-radius: 6px; font-weight: bold; }"


def _base_style(key: str) -> str:
    """Grey: a screen with boxes under it. Green: a screen at the end of its branch. Blue: a panel. Purple: a view."""
    if key in PANELS:
        return _PANEL_STYLE
    if key in VIEWS:
        return _VIEW_STYLE
    screens_below = [child for child in _children(key) if child not in PANELS and child not in VIEWS]  # panels and views do not count
    return _BRANCH_STYLE if screens_below else _LEAF_STYLE


def _trans_text(record) -> str:
    if not record.trans:
        return ""
    return "\n".join(f"{label(t.phrase)}  →  {_NAMES.get(t.goes_to, t.goes_to)}" for t in record.trans)


def _parent_text(record) -> str:
    return _NAMES.get(record.parent, "") if record.parent else ""


def _always_table() -> QWidget:
    """The always-listening phrases, in their own table to the right of the screen table."""
    page = QWidget()
    layout = QVBoxLayout(page)
    title = QLabel("<b>Always listening, every screen</b>")
    layout.addWidget(title)
    # The same list the recognizer listens to: GLOBAL plus every command no screen claims.
    always = [phrase for phrase in recognizer_setup()[0] if primary(phrase) == phrase]
    table = QTableWidget(len(always), 3)
    table.setHorizontalHeaderLabels(["Say", "Also say", "What it does"])
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setWordWrap(True)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    for row, phrase in enumerate(always):
        table.setItem(row, 0, QTableWidgetItem(primary(phrase)))
        table.setItem(row, 1, QTableWidgetItem("\n".join(aliases_of(primary(phrase)))))
        table.setItem(row, 2, QTableWidgetItem(_DESCRIPTIONS.get(primary(phrase), "")))
    table.setMinimumWidth(460)
    layout.addWidget(table, stretch=1)
    QTimer.singleShot(0, table.resizeRowsToContents)  # after the window has its width, so wrapped text fits
    return page


def _table_page() -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    group_names = list(GROUPS)
    columns = ("Screen", "Parent", "Transitions", *group_names)
    table = QTableWidget(len(SCREEN_RECORDS), len(columns))
    table.setHorizontalHeaderLabels(list(columns))
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    table.setWordWrap(True)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

    for row, record in enumerate(SCREEN_RECORDS):
        cells = [record.name, _parent_text(record), _trans_text(record)]
        for group in group_names:
            cells.append("\n".join(label(p) for p in GROUPS[group]) if group in record.groups else "")
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            if column >= 3 and text:
                item.setBackground(_HAS)
            table.setItem(row, column, item)
    QTimer.singleShot(0, table.resizeRowsToContents)  # after the window has its width, so wrapped text fits
    layout.addWidget(table)
    return page


# Every tree box: screens, panels and views (a panel or view is a box under the screen it opens on).
# Each entry is key -> (name, note, parent).
_NODES: dict[str, tuple[str, str, str | None]] = {
    **{record.key: (record.name, record.note, record.parent) for record in SCREEN_RECORDS},
    **{key: (overlay_name(key), "panel", PANEL_PARENTS[key]) for key in PANELS},
    **{key: (overlay_name(key), "view", VIEW_PARENTS[key]) for key in VIEWS},
}


def _children(key: str, nodes: dict[str, tuple[str, str, str | None]] | None = None) -> list[str]:
    nodes = _NODES if nodes is None else nodes
    return [child for child, (_name, _note, parent) in nodes.items() if parent == key]


def _overlay_commands(key: str) -> list[tuple[str, str, str, bool]]:
    """The commands a panel's or view's grammar holds, in the same shape as _commands_for."""
    rows: list[tuple[str, str, str, bool]] = []
    digits_listed = False
    for phrase in overlay_phrases(key):
        if phrase in DIGIT_KEYS:
            if digits_listed:
                continue
            digits_listed = True
            rows.append(("zero to nine", "", _DESCRIPTIONS.get("zero", "panel"), _WIRED.get("zero", False)))
            continue
        rows.append(
            (
                phrase,
                "\n".join(aliases_of(phrase)),
                _DESCRIPTIONS.get(primary(phrase), "panel"),
                _WIRED.get(primary(phrase), False),
            )
        )
    return rows


def _commands_for(key: str) -> list[tuple[str, str, str, bool]]:
    """Every command the screen can handle: (primary phrase, secondary phrases, what it does, wired up).
    Secondary phrases are one string with a newline between each. A transition is wired up when it
    has a sequence to run; a command is wired up when its row in commands.py is."""
    record = RECORDS_BY_KEY[key]
    rows: list[tuple[str, str, str, bool]] = []
    for trans in record.trans:
        rows.append(
            (
                trans.phrase,
                "\n".join(trans.aliases or aliases_of(trans.phrase)),
                f"transition to child screen {_NAMES.get(trans.goes_to, trans.goes_to)}",
                bool(trans.sequence),
            )
        )
    for phrase in record.phrases:  # the screen's own commands, not transitions
        rows.append(
            (
                shown(phrase),
                "\n".join(aliases_of(phrase)),
                _DESCRIPTIONS.get(primary(phrase), record.name),
                _WIRED.get(primary(phrase), False),
            )
        )
    digits_listed = False
    for group in record.groups:
        for phrase in GROUPS[group]:
            if phrase in DIGIT_KEYS:
                if digits_listed:
                    continue  # the ten digit words share one row
                digits_listed = True
                rows.append(("zero to nine", "", _DESCRIPTIONS.get("zero", group), _WIRED.get("zero", False)))
                continue
            rows.append(
                (
                    shown(phrase),
                    "\n".join(aliases_of(phrase)),
                    _DESCRIPTIONS.get(primary(phrase), group),
                    _WIRED.get(primary(phrase), False),
                )
            )
    return rows


def phrase_rows(phrases, default_text: str) -> list[tuple[str, str, str, bool]]:
    """Rows for a plain list of phrases (such as the global set), in the same columns as the screen tables."""
    rows: list[tuple[str, str, str, bool]] = []
    seen: set[str] = set()
    for phrase in phrases:
        if primary(phrase) != phrase or phrase in seen:
            continue  # aliases are shown on their primary's row
        seen.add(phrase)
        rows.append(
            (
                phrase,
                "\n".join(aliases_of(phrase)),
                _DESCRIPTIONS.get(phrase, default_text),
                _WIRED.get(phrase, False),
            )
        )
    return rows


def current_rows() -> tuple[str, list[tuple[str, str, str, bool]]]:
    """What is listening right now: the open panel's or view's commands, else the screen's, else nothing."""
    panel = current_panel() or current_view()
    if panel:
        return overlay_name(panel), _overlay_commands(panel)
    key = current_screen()
    if key in RECORDS_BY_KEY:
        return RECORDS_BY_KEY[key].name, _commands_for(key)
    return "GSPro (screen not known)", []


_NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
# Each family of nine numbered commands (one row per row of the course list) is shown as one line with a range.
_NUMBERED_FAMILIES: tuple[tuple[tuple[str, ...], str], ...] = (
    (tuple(f"play row {word} now" for word in _NUMBER_WORDS), "play row [1-9] now"),
    (tuple(f"play row {word}" for word in _NUMBER_WORDS), "play row [1-9]"),
    (tuple(f"download row {word} now" for word in _NUMBER_WORDS), "download row [1-9] now"),
    (tuple(f"download row {word}" for word in _NUMBER_WORDS), "download row [1-9]"),
    (tuple(f"show notes {word}" for word in _NUMBER_WORDS), "show notes [1-9]"),
    (tuple(f"toggle favorite row {word}" for word in _NUMBER_WORDS), "toggle favorite row [1-9]"),
    (tuple(f"shadow {word}" for word in ("one", "two", "three", "four", "five")), "shadow [1-5]"),
)


def collapse_names(names: list[str]) -> list[str]:
    """The same collapse for a plain list of phrases (the Active commands columns): a complete family is shown once
    as its range, where its first member was."""
    for members, shown_as in _NUMBERED_FAMILIES:
        found = [index for index, name in enumerate(names) if name in members]
        if len(found) != len(members):
            continue
        dropped = set(found[1:])
        names = [shown_as if index == found[0] else name for index, name in enumerate(names) if index not in dropped]
    return names


def _collapse_numbered(rows: list[tuple[str, str, str, bool]]) -> list[tuple[str, str, str, bool]]:
    """Replace each complete family of nine numbered rows with one row, shown with a [1-9] range. A family with
    any row missing is left as it is."""
    for members, shown_as in _NUMBERED_FAMILIES:
        found = [index for index, row in enumerate(rows) if row[0] in members]
        if len(found) != len(members):
            continue
        first = rows[found[0]]
        collapsed = (
            shown_as,
            first[1],
            re.sub(r"\brow 1\b", "rows 1-9", first[2]),
            all(rows[index][3] for index in found),
        )
        dropped = set(found[1:])
        rows = [collapsed if index == found[0] else row for index, row in enumerate(rows) if index not in dropped]
    return rows


def fill_table(table: QTableWidget, rows: list[tuple[str, str, str, bool]]) -> None:
    """Fill a table with the four columns (Say, Also say, What it does, Wired up) from rows."""
    rows = _collapse_numbered(rows)
    table.setRowCount(len(rows))
    for row, (say, also, what, wired) in enumerate(rows):
        table.setItem(row, 0, QTableWidgetItem(say))
        table.setItem(row, 1, QTableWidgetItem(also))
        table.setItem(row, 2, QTableWidgetItem(what))
        table.setItem(row, 3, QTableWidgetItem("yes" if wired else "no"))
    table.resizeRowsToContents()


def _place(
    key: str,
    depth: int,
    leaf_count: list[int],
    positions: dict[str, tuple[float, float]],
    nodes: dict[str, tuple[str, str, str | None]] | None = None,
    leaf_gap: float = LEAF_GAP,
    level_gap: float = LEVEL_GAP,
) -> float:
    """Tidy layout: leaves sit side by side in order; each parent centers over its children."""
    kids = _children(key, nodes)
    if not kids:
        x = leaf_count[0] * leaf_gap
        leaf_count[0] += 1
    else:
        xs = [_place(kid, depth + 1, leaf_count, positions, nodes, leaf_gap, level_gap) for kid in kids]
        x = (xs[0] + xs[-1]) / 2
    positions[key] = (x, depth * level_gap)
    return x


def _tree_view(
    nodes: dict[str, tuple[str, str, str | None]],
    buttons: dict[str, QPushButton],
    on_click=None,
    node_w: int = NODE_W,
    node_h: int = NODE_H,
    leaf_gap: float = LEAF_GAP,
    level_gap: float = LEVEL_GAP,
) -> QGraphicsView:
    """The tree diagram: a box per node, joined to its parent. nodes is every box it shows (screens, or screens
    with panels and views). Each box is added to buttons; on_click(key) runs when a box is clicked. The sizes and
    gaps default to the commands window's; the sync window passes its own."""
    positions: dict[str, tuple[float, float]] = {}
    _place(ROOT.key, 0, [0], positions, nodes, leaf_gap, level_gap)

    view = QGraphicsView()
    scene = QGraphicsScene(view)  # owned by the view, so it is not freed when this function ends
    view.setScene(scene)
    # Connecting lines first, so the boxes sit on top of them.
    for key, (_name, _note, parent) in nodes.items():
        if parent is None:
            continue
        px, py = positions[parent]
        cx, cy = positions[key]
        scene.addLine(px, py + node_h, cx, cy, QPen(QColor("#555555"), 2))
    for key, (name, note, _parent) in nodes.items():
        x, y = positions[key]
        button = QPushButton(f"{name}\n({note})" if note else name)
        button.setFixedSize(node_w, node_h)
        button.setStyleSheet(_base_style(key))
        buttons[key] = button
        if on_click is not None:
            button.clicked.connect(lambda _checked=False, key=key: on_click(key))
        proxy = scene.addWidget(button)
        proxy.setPos(x - node_w / 2, y)

    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(360)
    view.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
    return view


def _tree_page() -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)

    commands_title = QLabel()
    commands_title.setStyleSheet("font-weight: bold; padding-top: 6px;")
    commands = QTableWidget(0, 4)
    commands.setHorizontalHeaderLabels(["Say", "Also say", "What it does", "Wired up"])
    commands.verticalHeader().setVisible(False)
    commands.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    commands.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    commands.setWordWrap(True)
    commands.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    commands.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    commands.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    commands.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    commands.setMinimumHeight(220)

    buttons: dict[str, QPushButton] = {}

    def highlight(key: str) -> None:
        """Outline the box for the screen whose commands are listed."""
        for name, button in buttons.items():
            base = _base_style(name)
            outline = " QPushButton { border: 3px solid #ffb300; }" if name == key else ""
            button.setStyleSheet(base + outline)

    def show(key: str) -> None:
        highlight(key)
        is_overlay = key in PANELS or key in VIEWS
        rows = _overlay_commands(key) if is_overlay else _commands_for(key)
        name = _NODES[key][0]
        kind = "Panel" if key in PANELS else "View" if key in VIEWS else "Commands on"
        commands_title.setText(f"{kind} {name} ({len(rows)})")
        commands.setRowCount(len(rows))
        for row, (phrase, also, detail, wired) in enumerate(rows):
            commands.setItem(row, 0, QTableWidgetItem(phrase))
            commands.setItem(row, 1, QTableWidgetItem(also))
            commands.setItem(row, 2, QTableWidgetItem(detail))
            status = QTableWidgetItem("Yes" if wired else "No")
            if not wired:
                for column in range(3):
                    commands.item(row, column).setBackground(_NOT_WIRED)
                status.setBackground(_NOT_WIRED)
            commands.setItem(row, 3, status)
        QTimer.singleShot(0, commands.resizeRowsToContents)

    layout.addWidget(_tree_view(_NODES, buttons, show), stretch=1)

    # Bottom of the Tree tab: the commands for the screen you are on, and the always-on commands.
    per_screen = QWidget()
    per_screen_layout = QVBoxLayout(per_screen)
    per_screen_layout.addWidget(commands_title)
    per_screen_layout.addWidget(commands)
    bottom = QTabWidget()
    bottom.addTab(per_screen, "Commands")
    bottom.addTab(_always_table(), "Always on")
    layout.addWidget(bottom)
    show(ROOT.key)  # start on home so the list is never empty

    # Follow the app: when GSPro moves to another screen, show that screen's commands.
    # A click on a box stays until the next screen change.
    last_seen: dict[str, str | None] = {"screen": None}

    def follow() -> None:
        # An open panel or view comes first: its box and commands show until it closes.
        target = current_panel() or current_view() or current_screen()
        if target == last_seen["screen"] or target not in _NODES:
            return
        last_seen["screen"] = target
        show(target)

    timer = QTimer(page)
    timer.timeout.connect(follow)
    timer.start(FOLLOW_MS)
    return page


def build_screen_table(parent: QWidget | None = None) -> QMainWindow:
    """A window of its own, not a dialog: it resizes, moves and minimises like any app window."""
    window = QMainWindow(parent)
    window.setWindowTitle("Commands")
    window.resize(1500, 860)
    central = QWidget()
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)

    tabs = QTabWidget()
    tabs.addTab(_table_page(), "Table")
    tabs.addTab(_tree_page(), "Tree")
    from app.commands_page import build_active_page  # imported here: commands_page imports this module
    from app.overlap_page import build_overlap_page  # imported here, like build_active_page

    tabs.addTab(build_active_page(), "Active commands")
    tabs.addTab(build_overlap_page(), "Analyze overlap")
    tabs.setCurrentIndex(2)  # Active commands opens first: it shows what is listening now
    layout.addWidget(tabs, stretch=1)

    problems = check()
    if problems:
        status = QLabel("<b>Does not match the tree:</b><br>" + "<br>".join(problems))
        status.setStyleSheet("background-color: #f5d6d6; padding: 6px;")
    else:
        status = QLabel("Matches the screen tree and commands.")
        status.setStyleSheet("background-color: #d6f5d6; padding: 6px;")
    status.setWordWrap(True)
    layout.addWidget(status)

    close = QPushButton("Close")
    close.clicked.connect(window.close)
    layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
    return window


# The sync help window: the same tree, with only the actual screens (no panels or views).
SYNC_WINDOW_W, SYNC_WINDOW_H = 1400, 820  # bigger than the commands window, so the tree is read without scrolling
SYNC_NODE_W, SYNC_NODE_H = 132, 56  # tighter boxes than the commands tree
SYNC_LEAF_GAP, SYNC_LEVEL_GAP = 150, 100  # the gaps between boxes, across and down
_SCREEN_NODES: dict[str, tuple[str, str, str | None]] = {
    record.key: (record.name, record.note, record.parent) for record in SCREEN_RECORDS
}


class _SyncWindow(QMainWindow):
    """Closing it with its X also closes the sync help, so the app stops listening for screen names."""

    def __init__(self, on_close) -> None:
        super().__init__()
        self._on_close = on_close
        # Stays above GSPro: the app puts GSPro in front when it sends a command, which would otherwise bury this window.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowTitle("Sync help: say a screen name to sync to it, or cancel")
        self.resize(SYNC_WINDOW_W, SYNC_WINDOW_H)
        from app.gspro_boxes import BOX_COLOUR  # the overlay's box colour, so the X box matches the cancel box on screen

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        top = QHBoxLayout()
        top.addStretch(1)
        cancel = QPushButton("X")  # closes the window, and the sync help with it
        cancel.setFixedSize(36, 30)
        cancel.setStyleSheet(f"QPushButton {{ border: 3px solid {BOX_COLOUR.name()}; background: white; font-weight: bold; }}")
        cancel.clicked.connect(self.close)
        top.addWidget(cancel)
        layout.addLayout(top)
        # Tighter boxes and gaps than the commands window, so the whole tree fits without scrollbars.
        tree = _tree_view(_SCREEN_NODES, {}, None, SYNC_NODE_W, SYNC_NODE_H, SYNC_LEAF_GAP, SYNC_LEVEL_GAP)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tree.setMinimumHeight(0)
        layout.addWidget(tree, stretch=1)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt name)
        if self._on_close is not None:
            self._on_close()
        super().closeEvent(event)


_sync_window: _SyncWindow | None = None


def _move_to_gspro(window: QMainWindow) -> None:
    """Put the window just inside GSPro's top left corner, so it opens on GSPro's monitor. Placed in physical pixels
    with Windows directly, as the grid does (Qt converts positions with each screen's scaling). Does nothing if
    GSPro is not there."""
    import ctypes

    from app.connector_ui import client_rect, find_window
    from app.gspro_ui import GSPRO_TITLE

    hwnd = find_window(GSPRO_TITLE)
    if hwnd is None:
        return
    left, top, _right, _bottom = client_rect(hwnd)
    swp_nosize, swp_noactivate, swp_showwindow = 0x0001, 0x0010, 0x0040
    ctypes.windll.user32.SetWindowPos(
        int(window.winId()), 0, left + 40, top + 40, 0, 0, swp_nosize | swp_noactivate | swp_showwindow
    )


def _center_on_monitor(window: QMainWindow) -> None:
    """Centre the window on the monitor it is on (after _move_to_gspro, that is GSPro's monitor)."""
    screen_geometry = window.screen().availableGeometry()
    top_left = screen_geometry.center() - window.rect().center()
    window.move(top_left)


def show_sync_tree(on_close=None) -> None:
    """Open the sync help tree, or bring it to the front. on_close runs when its X closes it."""
    global _sync_window
    if _sync_window is None:
        _sync_window = _SyncWindow(on_close)
    _sync_window.show()
    _move_to_gspro(_sync_window)  # after show, so Windows has the window's handle
    _center_on_monitor(_sync_window)
    _sync_window.raise_()
    _sync_window.activateWindow()


def hide_sync_tree() -> None:
    """Close the sync help tree from the app (cancel, or a screen name said). Its X is handled by closeEvent."""
    if _sync_window is not None:
        _sync_window.hide()


_open: QMainWindow | None = None  # kept so the window is not garbage collected while it is open


def show_screen_table(parent: QWidget | None = None) -> None:
    """Open the screen table as a free window. It does not block the main app, so commands can
    still be tested on the Overview page while it is open."""
    global _open
    if _open is not None and _open.isVisible():
        _open.raise_()
        _open.activateWindow()
        return
    # No parent: a window with a parent is kept above that parent on Windows, which hides the main
    # app behind it. Without one, the table is an ordinary window and the main app can come forward.
    _open = build_screen_table(None)
    restore(_open, COMMANDS_KEY)  # where it was last closed or moved, if that is still on screen
    remember(_open, COMMANDS_KEY)
    _open.show()
