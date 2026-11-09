"""Course names for the "play <name>" grammar, kept in our own database.

The course table in gspraudio.db is copied from GSPro's CourseRepoCourse table when the
Developer page's sync button is pressed. The copy replaces our list each time, and
GSPro Multi Range is left out because it is not a course. The grammar reads our table, so
GSPro's database is not needed at startup.

Names are made speakable: "&" is said as "and", hyphens become spaces, and other
punctuation is dropped, so "Coeur d'Alene" is spoken as "coeur dalene".
"""

import logging
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from app.players import db_path

log = logging.getLogger(__name__)

PREFIX = "play"  # the same words as commands.COURSE_PHRASE
GSPRO_DB = Path.home() / "AppData" / "LocalLow" / "GSPro" / "GSPro" / "GSPro.db"
NOT_COURSES = frozenset({"GSPro Multi Range"})  # GSPro Practice Facility is a playable course


def spoken(name: str) -> str:
    text = name.replace("&", " and ").replace("-", " ").lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return " ".join(text.split())


def _ours() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.execute("CREATE TABLE IF NOT EXISTS course (name TEXT PRIMARY KEY, spoken TEXT NOT NULL)")
    return con


def _read_gspro_names() -> list[str]:
    con = sqlite3.connect(f"file:{GSPRO_DB.as_posix()}?mode=ro", uri=True)
    try:
        return [name for (name,) in con.execute("SELECT Name FROM CourseRepoCourse") if name]
    finally:
        con.close()


def sync_from_gspro() -> int:
    """Replace our course list with GSPro's. Returns how many courses were saved.
    Raises sqlite3.Error if GSPro's database can't be read."""
    rows: dict[str, str] = {}
    for name in _read_gspro_names():
        if name in NOT_COURSES:
            continue
        words = spoken(name)
        if words:
            rows[name] = words
    con = _ours()
    try:
        with con:
            con.execute("DELETE FROM course")
            con.executemany("INSERT INTO course (name, spoken) VALUES (?, ?)", rows.items())
    finally:
        con.close()
    course_phrases.cache_clear()
    log.info("synced %d courses from GSPro", len(rows))
    return len(rows)


def _saved_words() -> list[str]:
    con = _ours()
    try:
        return [row[0] for row in con.execute("SELECT spoken FROM course ORDER BY spoken")]
    finally:
        con.close()


@lru_cache(maxsize=1)
def course_phrases() -> tuple[str, ...]:
    """"play <spoken name>" and "play <spoken name> now" for each saved course. If our list is
    empty (first run), it is copied from GSPro once."""
    try:
        words = _saved_words()
        if not words:
            sync_from_gspro()
            words = _saved_words()
    except sqlite3.Error:
        log.exception("could not read the course list")
        return ()
    phrases: list[str] = []
    for word in words:
        phrases.append(f"{PREFIX} {word}")
        phrases.append(f"{PREFIX} {word} now")  # "play <name> now" also starts the round
    unique = tuple(dict.fromkeys(phrases))
    log.info("course grammar: %d course names", len(unique) // 2)
    return unique
