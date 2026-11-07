"""Small saved preferences. Stored in gspraudio.db's app_state table under a 'pref.' prefix."""

from app.players import connect

_PREFIX = "pref."


def get_pref(key: str, default: str) -> str:
    with connect() as con:
        row = con.execute(
            "SELECT value FROM app_state WHERE key = ?", (_PREFIX + key,)
        ).fetchone()
    return default if row is None else row["value"]


def set_pref(key: str, value: str) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_PREFIX + key, value),
        )


def get_bool(key: str, default: bool) -> bool:
    return get_pref(key, "1" if default else "0") == "1"


def set_bool(key: str, value: bool) -> None:
    set_pref(key, "1" if value else "0")
