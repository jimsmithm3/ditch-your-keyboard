"""Local players and the clubs in each player's bag."""

import json
import sqlite3

from app.paths import resource_path, writable_dir


def db_path():
    return writable_dir() / "gspraudio.db"


def _catalog() -> list[dict]:
    data = json.loads(resource_path("resources", "gspro_clubs.json").read_text(encoding="utf-8"))
    return data["clubs"]


def display_name(club: dict) -> str:
    return club["spoken"] or club["name"]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS player (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS player_club (
            player_id INTEGER NOT NULL REFERENCES player(id),
            club_index INTEGER NOT NULL,
            active INTEGER NOT NULL,
            nickname TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (player_id, club_index)
        );
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    columns = {row[1] for row in con.execute("PRAGMA table_info(player)")}
    if "bag_id" not in columns:
        con.execute("ALTER TABLE player ADD COLUMN bag_id INTEGER")
    return con


def list_players() -> list[tuple[int, str]]:
    with connect() as con:
        rows = con.execute("SELECT id, name FROM player ORDER BY name").fetchall()
    return [(int(row["id"]), row["name"]) for row in rows]


def active_player_id() -> int | None:
    with connect() as con:
        row = con.execute("SELECT value FROM app_state WHERE key = 'player'").fetchone()
    if row is None:
        return None
    return int(row["value"])


def set_active_player(player_id: int) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO app_state (key, value) VALUES ('player', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(player_id),),
        )


def player_bag_id(player_id: int) -> int | None:
    with connect() as con:
        row = con.execute("SELECT bag_id FROM player WHERE id = ?", (player_id,)).fetchone()
    if row is None or row["bag_id"] is None:
        return None
    return int(row["bag_id"])


def active_club_indexes(player_id: int) -> set[int]:
    with connect() as con:
        rows = con.execute(
            "SELECT club_index FROM player_club WHERE player_id = ? AND active = 1",
            (player_id,),
        ).fetchall()
    return {int(row["club_index"]) for row in rows}


def set_player_bag(player_id: int, bag_id: int | None) -> None:
    with connect() as con:
        con.execute("UPDATE player SET bag_id = ? WHERE id = ?", (bag_id, player_id))


def create_player(
    name: str,
    active_indexes: set[int],
    nicknames: dict[int, str],
    bag_id: int | None = None,
) -> int:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Player name is empty")
    with connect() as con:
        cur = con.execute("INSERT INTO player (name, bag_id) VALUES (?, ?)", (cleaned, bag_id))
        player_id = int(cur.lastrowid)
        for club in _catalog():
            index = int(club["index"])
            con.execute(
                "INSERT INTO player_club (player_id, club_index, active, nickname) VALUES (?, ?, ?, ?)",
                (player_id, index, 1 if index in active_indexes else 0, nicknames.get(index, "").strip()),
            )
    set_active_player(player_id)
    return player_id


def bag_names(player_id: int) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    """Active club names in enum order, plus nickname phrases for each."""
    by_index = {int(club["index"]): club for club in _catalog()}
    names: list[str] = []
    phrases: dict[str, tuple[str, ...]] = {}
    with connect() as con:
        rows = con.execute(
            "SELECT club_index, nickname FROM player_club WHERE player_id = ? AND active = 1 ORDER BY club_index",
            (player_id,),
        ).fetchall()
    for row in rows:
        club = by_index.get(int(row["club_index"]))
        if club is None:
            continue
        name = display_name(club)
        names.append(name)
        nickname = (row["nickname"] or "").strip().lower()
        if nickname:
            phrases[name] = (nickname,)
    return names, phrases


def nickname_phrases(player_id: int | None = None) -> tuple[str, ...]:
    player_id = active_player_id() if player_id is None else player_id
    if player_id is None:
        return ()
    _names, phrases = bag_names(player_id)
    return tuple(phrase for group in phrases.values() for phrase in group)


def set_active_names(player_id: int, enabled: list[str]) -> list[str]:
    """Turn catalog clubs on or off. Clubs with no spoken name keep their flag."""
    chosen = set(enabled)
    catalog = _catalog()
    spoken = {display_name(club) for club in catalog if club["spoken"]}
    with connect() as con:
        current = {
            int(row["club_index"]): int(row["active"])
            for row in con.execute(
                "SELECT club_index, active FROM player_club WHERE player_id = ?",
                (player_id,),
            )
        }
        for club in catalog:
            index = int(club["index"])
            name = display_name(club)
            if name in spoken:
                active = 1 if name in chosen else 0
            else:
                active = current.get(index, 0)
            con.execute(
                "UPDATE player_club SET active = ? WHERE player_id = ? AND club_index = ?",
                (active, player_id, index),
            )
    names, _phrases = bag_names(player_id)
    return names
