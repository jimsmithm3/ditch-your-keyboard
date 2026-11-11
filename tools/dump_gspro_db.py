"""Dump every table in GSPro.db to CSV, read-only, so later dumps can be compared.

Usage: python tools/dump_gspro_db.py <name>
Writes to db_dumps/<name>/<table>.csv and a _tables.txt listing the row counts.
The game's database is opened read-only and is never written.
"""

import csv
import sqlite3
import sys
from pathlib import Path

DB = Path.home() / "AppData" / "LocalLow" / "GSPro" / "GSPro" / "GSPro.db"
ROOT = Path(__file__).resolve().parent.parent / "db_dumps"


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    out = ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    try:
        tables = [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        summary = []
        for table in tables:
            cursor = con.execute(f'SELECT * FROM "{table}"')
            columns = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
            with (out / f"{table}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerows(rows)
            summary.append(f"{table}\t{len(rows)} rows\t{len(columns)} columns")
        (out / "_tables.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
        print(f"Dumped {len(tables)} tables from {DB} to {out}")
        print("\n".join(summary))
    finally:
        con.close()


if __name__ == "__main__":
    main()
