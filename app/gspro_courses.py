"""Course names for the "play course <name>" grammar, kept in our own database.

The course table in ditch-your-keyboard.db is copied from GSPro's CourseRepoCourse table when the
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

GSPRO_DB = Path.home() / "AppData" / "LocalLow" / "GSPro" / "GSPro" / "GSPro.db"
NOT_COURSES = frozenset({"GSPro Multi Range"})  # GSPro Practice Facility is a playable course


def spoken(name: str) -> str:
    text = name.replace("&", " and ").replace("-", " ").lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return " ".join(text.split())


_COLUMNS = ("location", "designer")  # GSPro's search also matches these, so we keep them too
_needs_sync = False  # set when the table had to be changed to hold them; the list is then copied again


def _ours() -> sqlite3.Connection:
    global _needs_sync
    con = sqlite3.connect(db_path())
    con.execute(
        "CREATE TABLE IF NOT EXISTS course (name TEXT PRIMARY KEY, spoken TEXT NOT NULL, "
        "location TEXT NOT NULL DEFAULT '', designer TEXT NOT NULL DEFAULT '')"
    )
    have = {row[1] for row in con.execute("PRAGMA table_info(course)")}
    for column in _COLUMNS:
        if column not in have:
            con.execute(f"ALTER TABLE course ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            _needs_sync = True
    return con


def _key(text: str) -> str:
    """Letters and digits only, lower case: spaces and punctuation are not part of a match."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _read_gspro_courses() -> list[tuple[str, str, str]]:
    """(name, location, designer) for each course in GSPro's table. Read-only."""
    con = sqlite3.connect(f"file:{GSPRO_DB.as_posix()}?mode=ro", uri=True)
    try:
        return [
            (name, location or "", designer or "")
            for name, location, designer in con.execute(
                "SELECT Name, CourseLocation, CourseDesigner FROM CourseRepoCourse"
            )
            if name
        ]
    finally:
        con.close()


def gspro_course_count() -> int:
    """How many rows GSPro's course table has now. A download adds one row when it finishes, so the count going
    up by one is how the app knows the download is done. Read-only. Raises sqlite3.Error if the database is busy."""
    con = sqlite3.connect(f"file:{GSPRO_DB.as_posix()}?mode=ro", uri=True)
    try:
        return int(con.execute("SELECT COUNT(*) FROM CourseRepoCourse").fetchone()[0])
    finally:
        con.close()


def sync_from_gspro() -> int:
    """Replace our course list with GSPro's. Returns how many courses were saved.
    Raises sqlite3.Error if GSPro's database can't be read."""
    global _needs_sync
    rows: list[tuple[str, str, str, str]] = []
    for name, location, designer in _read_gspro_courses():
        if name in NOT_COURSES:
            continue
        words = spoken(name)
        if words:
            rows.append((name, words, location, designer))
    con = _ours()
    try:
        with con:
            con.execute("DELETE FROM course")
            con.executemany("INSERT INTO course (name, spoken, location, designer) VALUES (?, ?, ?, ?)", rows)
    finally:
        con.close()
    _needs_sync = False  # the table now holds the location and designer
    course_phrases.cache_clear()
    log.info("synced %d courses from GSPro", len(rows))
    return len(rows)


def course_names() -> list[str]:
    """The course names as GSPro spells them (from our copy)."""
    con = _ours()
    try:
        return [name for (name,) in con.execute("SELECT name FROM course ORDER BY name")]
    finally:
        con.close()


def courses_matching(typed: str) -> list[str]:
    """The courses GSPro's search would show for what is typed: the typed letters are found in the name, the
    location or the designer, as GSPro's filter does. Spaces and punctuation are ignored."""
    want = _key(typed)
    if not want:
        return []
    con = _ours()
    try:
        return [
            name
            for name, location, designer in con.execute("SELECT name, location, designer FROM course ORDER BY name")
            if any(want in _key(field) for field in (name, location, designer))
        ]
    finally:
        con.close()


def course_key(name: str) -> str:
    """The name as the letters the filter needs: spaces and punctuation dropped, lower case."""
    return _key(name)


def _saved_words() -> list[str]:
    con = _ours()
    try:
        return [row[0] for row in con.execute("SELECT spoken FROM course ORDER BY spoken")]
    finally:
        con.close()


@lru_cache(maxsize=1)
def course_phrases() -> tuple[str, ...]:
    """"play course <spoken name>" and "play course <spoken name> now" for each saved course. If our list is
    empty (first run), or was changed to hold the location and designer, it is copied from GSPro."""
    try:
        words = _saved_words()
        if not words or _needs_sync:
            sync_from_gspro()
            words = _saved_words()
    except sqlite3.Error:
        log.exception("could not read the course list")
        return ()
    phrases: list[str] = []
    for word in words:
        phrases.append(f"play course {word}")
        phrases.append(f"play course {word} now")  # "play <name> now" also starts the round
    unique = tuple(dict.fromkeys(phrases))
    log.info("course grammar: %d course names", len(unique) // 2)
    return unique
