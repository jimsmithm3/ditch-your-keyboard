"""Choose the player for this session, or create one from a GSPro bag."""

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.bag import DEFAULT_BAG
from app.gspro_bag import GsproBag, load_bags
from app.players import (
    active_club_indexes,
    active_player_id,
    create_player,
    display_name,
    list_players,
    player_bag_id,
    set_active_player,
    set_player_bag,
    _catalog,
)


def choose_player(parent: QWidget, pick: bool = False) -> int | None:
    """Use the last player, and that player's bag. pick=True always asks."""
    players = list_players()
    known = {player_id for player_id, _name in players}
    saved = active_player_id()
    if not pick and saved in known:
        return saved
    if len(players) == 1 and not pick:
        set_active_player(players[0][0])
        return players[0][0]

    dialog = QDialog(parent)
    dialog.setWindowTitle("Player")
    layout = QVBoxLayout(dialog)
    message = QLabel("")
    message.setWordWrap(True)
    chosen: list[int] = []

    gspro: list[GsproBag] = []
    try:
        gspro = load_bags()
    except (OSError, sqlite3.Error):
        gspro = []

    if players:
        layout.addWidget(QLabel("Who is playing?"))
        picker = QComboBox()
        current = active_player_id()
        for player_id, name in players:
            picker.addItem(name, player_id)
            if player_id == current:
                picker.setCurrentIndex(picker.count() - 1)
        layout.addWidget(picker)
        layout.addWidget(QLabel("Bag"))
        player_bag = QComboBox()
        player_bag.addItem("No GSPro bag", None)
        for bag in gspro:
            player_bag.addItem(bag.name or f"Bag {bag.id}", bag.id)
        layout.addWidget(player_bag)

        def show_player_bag() -> None:
            player_id = int(picker.currentData())
            bag_id = player_bag_id(player_id)
            if bag_id is None:
                bag_id = _matching_bag_id(player_id, gspro)
            index = player_bag.findData(bag_id)
            player_bag.setCurrentIndex(index if index >= 0 else 0)

        picker.currentIndexChanged.connect(lambda _index: show_player_bag())
        show_player_bag()
        use = QPushButton("Use player")
        layout.addWidget(use)

        def on_use() -> None:
            player_id = int(picker.currentData())
            bag_id = player_bag.currentData()
            if bag_id != player_bag_id(player_id):
                set_player_bag(player_id, int(bag_id) if bag_id is not None else None)
            set_active_player(player_id)
            chosen.append(player_id)
            dialog.accept()

        use.clicked.connect(on_use)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

    layout.addWidget(QLabel("New player"))
    name_box = QLineEdit()
    name_box.setPlaceholderText("Name")
    layout.addWidget(name_box)
    bag_picker = QComboBox()
    bag_picker.addItem("No GSPro bag", None)
    for bag in gspro:
        bag_picker.addItem(bag.name or f"Bag {bag.id}", bag.id)
    layout.addWidget(bag_picker)
    layout.addWidget(message)

    row = QHBoxLayout()
    create = QPushButton("Create")
    cancel = QPushButton("Cancel")
    row.addWidget(create)
    row.addWidget(cancel)
    layout.addLayout(row)

    def on_create() -> None:
        bag_id = bag_picker.currentData()
        bag = next((item for item in gspro if item.id == bag_id), None)
        try:
            player_id = create_player(name_box.text(), *_seed(bag), bag.id if bag else None)
        except Exception as exc:
            message.setText(str(exc))
            return
        chosen.append(player_id)
        dialog.accept()

    create.clicked.connect(on_create)
    cancel.clicked.connect(dialog.reject)
    if dialog.exec() != QDialog.DialogCode.Accepted or not chosen:
        return None
    return chosen[-1]


def _matching_bag_id(player_id: int, bags: list[GsproBag]) -> int | None:
    indexes = active_club_indexes(player_id)
    for bag in bags:
        found = {int(club.get("GSProClubIndex", -1)) for club in bag.clubs}
        found.discard(-1)
        if found and found == indexes:
            return bag.id
    return None


def _seed(bag: GsproBag | None) -> tuple[set[int], dict[int, str]]:
    if bag is None:
        wanted = set(DEFAULT_BAG)
        indexes = {int(club["index"]) for club in _catalog() if display_name(club) in wanted}
        return indexes, {}
    indexes: set[int] = set()
    nicknames: dict[int, str] = {}
    for club in bag.clubs:
        index = int(club.get("GSProClubIndex", -1))
        if index < 0:
            continue
        indexes.add(index)
        nicknames[index] = str(club.get("ClubNickName") or "")
    return indexes, nicknames
