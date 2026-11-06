"""Read and update shortcut names in GSPro's LockerBag table."""

import json
import sqlite3
from pathlib import Path

from app.paths import resource_path

_YARDS = 0.9144


def db_path() -> Path:
    return Path.home() / "AppData" / "LocalLow" / "GSPro" / "GSPro" / "GSPro.db"


def club_names() -> dict[int, str]:
    data = json.loads(resource_path("resources", "gspro_clubs.json").read_text(encoding="utf-8"))
    return {int(row["index"]): row["name"] for row in data["clubs"]}


class GsproBag:
    def __init__(self, bag_id: int, name: str, clubs: list[dict]) -> None:
        self.id = bag_id
        self.name = name
        self.clubs = clubs


def load_bags() -> list[GsproBag]:
    path = db_path()
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        rows = con.execute("SELECT ID, BagName, Clubs FROM LockerBag ORDER BY BagName").fetchall()
    bags: list[GsproBag] = []
    for bag_id, name, raw in rows:
        bags.append(GsproBag(int(bag_id), name or "", json.loads(raw or "[]")))
    return bags


def save_nicknames(bag_id: int, nicknames: list[str]) -> None:
    """Rewrite one locker row, changing ClubNickName only."""
    path = db_path()
    with sqlite3.connect(path, timeout=2) as con:
        row = con.execute("SELECT Clubs FROM LockerBag WHERE ID = ?", (bag_id,)).fetchone()
        if row is None:
            raise LookupError(f"bag {bag_id} is gone")
        clubs = json.loads(row[0] or "[]")
        if len(clubs) != len(nicknames):
            raise ValueError("bag changed while it was open")
        for club, nickname in zip(clubs, nicknames):
            club["ClubNickName"] = nickname
        text = json.dumps(clubs, separators=(",", ":"))
        con.execute("UPDATE LockerBag SET Clubs = ? WHERE ID = ?", (text, bag_id))


def yards(meters: float) -> str:
    amount = float(meters) / _YARDS
    whole = round(amount)
    if abs(amount - whole) < 0.05:
        return str(whole)
    return f"{amount:.1f}"
