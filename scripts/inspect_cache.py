"""Inspect the local FastF1 HTTP cache SQLite DB (debug helper)."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CACHE = _REPO_ROOT / "fastf1_cache" / "fastf1_http_cache.sqlite"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-db",
        type=Path,
        default=_DEFAULT_CACHE,
        help=f"path to fastf1_http_cache.sqlite (default: {_DEFAULT_CACHE})",
    )
    args = parser.parse_args()
    db_path: Path = args.cache_db
    if not db_path.exists():
        raise SystemExit(f"cache DB not found: {db_path}")

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        print("table:", r)
    print("---")
    cur.execute("PRAGMA table_info(responses)")
    print("schema:", cur.fetchall())
    print("---")
    try:
        cur.execute(
            "SELECT cache_key, expires FROM responses WHERE url LIKE '%schedule%' LIMIT 10"
        )
        for r in cur.fetchall():
            print(r)
    except Exception:
        pass
    con.close()


if __name__ == "__main__":
    main()
