"""Screen table window, with two tabs: a table of screens by group, and a tree diagram.

Read-only for now. Table: one row per screen, one column per group; each cell lists the phrases
that group holds on that screen. Tree: a top-down diagram with Home at the top, its children
joined under it, and their children under those. Click a node to list every command that screen
can handle.

Rows, groups and the tree come from gspro_screens.py; the check at the bottom compares them
with the tree and commands.
"""

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

from app.commands import DIGIT_KEYS, ROWS, aliases_of, primary
from app.gspro_sequences import current_panel, current_screen
from app.gspro_screens import (
    GLOBAL,
    recognizer_setup,
    GROUPS,
    PANEL_NAMES,
    PANEL_PARENTS,
    PANELS,
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


def _base_style(key: str) -> str:
    """Grey: a screen with boxes under it. Green: a screen at the end of its branch. Blue: a panel."""
    if key in PANELS:
        return _PANEL_STYLE
    screens_below = [child for child in _children(key) if child not in PANELS]  # panels do not count
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


# Every tree box: screens, and panels (a panel is a box under the screen it opens on).
# Each entry is key -> (name, note, parent).
_NODES: dict[str, tuple[str, str, str | None]] = {
    **{record.key: (record.name, record.note, record.parent) for record in SCREEN_RECORDS},
    **{key: (PANEL_NAMES[key], "panel", PANEL_PARENTS[key]) for key in PANELS},
}


def _children(key: str) -> list[str]:
    return [child for child, (_name, _note, parent) in _NODES.items() if parent == key]


def _panel_commands(key: str) -> list[tuple[str, str, str, bool]]:
    """The commands a panel's grammar holds, in the same shape as _commands_for."""
    rows: list[tuple[str, str, str, bool]] = []
    digits_listed = False
    for phrase in PANELS[key]:
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
                    phrase,
                    "\n".join(aliases_of(phrase)),
                    _DESCRIPTIONS.get(primary(phrase), group),
                    _WIRED.get(primary(phrase), False),
                )
            )
    return rows


def _place(key: str, depth: int, leaf_count: list[int], positions: dict[str, tuple[float, float]]) -> float:
    """Tidy layout: leaves sit side by side in order; each parent centers over its children."""
    kids = _children(key)
    if not kids:
        x = leaf_count[0] * LEAF_GAP
        leaf_count[0] += 1
    else:
        xs = [_place(kid, depth + 1, leaf_count, positions) for kid in kids]
        x = (xs[0] + xs[-1]) / 2
    positions[key] = (x, depth * LEVEL_GAP)
    return x


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
        is_panel = key in PANELS
        rows = _panel_commands(key) if is_panel else _commands_for(key)
        name = _NODES[key][0]
        commands_title.setText(f"{'Panel' if is_panel else 'Commands on'} {name} ({len(rows)})")
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

    positions: dict[str, tuple[float, float]] = {}
    _place(ROOT.key, 0, [0], positions)

    view = QGraphicsView()
    scene = QGraphicsScene(view)  # owned by the view, so it is not freed when this function ends
    view.setScene(scene)
    # Connecting lines first, so the boxes sit on top of them.
    for key, (_name, _note, parent) in _NODES.items():
        if parent is None:
            continue
        px, py = positions[parent]
        cx, cy = positions[key]
        scene.addLine(px, py + NODE_H, cx, cy, QPen(QColor("#555555"), 2))
    for key, (name, note, _parent) in _NODES.items():
        x, y = positions[key]
        button = QPushButton(f"{name}\n({note})" if note else name)
        button.setFixedSize(NODE_W, NODE_H)
        button.setStyleSheet(_base_style(key))
        buttons[key] = button
        button.clicked.connect(lambda _checked=False, key=key: show(key))
        proxy = scene.addWidget(button)
        proxy.setPos(x - NODE_W / 2, y)

    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(360)
    view.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
    layout.addWidget(view, stretch=1)

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
        # An open panel comes first: its box and commands show until it closes.
        target = current_panel() or current_screen()
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
    tabs.setCurrentIndex(1)  # the Tree opens first: it shows what each screen can do
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
    _open.show()
