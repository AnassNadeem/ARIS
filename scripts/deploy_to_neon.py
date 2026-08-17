"""One-shot Neon deploy helper.

Reads `.env.cloud` at the repo root, points ARIS at the Neon Postgres URL it
contains, applies `db/schema.sql` plus migrations `002_weekend_data.sql` and
`003_sprint_session_type.sql`, ingests the 2024 season, and prints final row
counts. Idempotent — re-running is safe.

Usage (from the repo root, with .env.cloud already filled in):

    .venv\\Scripts\\python.exe scripts\\deploy_to_neon.py

Manual cloud-side steps that this script does NOT do:
  * Create the Neon project + grab the connection string.
  * Deploy the app on https://share.streamlit.io and paste the URL into the
    Secrets pane (see DEPLOY.md).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import dotenv_values  # noqa: E402

_SCHEMA_FILES = (
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "migrations" / "002_weekend_data.sql",
    ROOT / "db" / "migrations" / "003_sprint_session_type.sql",
)


def _load_cloud_env() -> str:
    """Return ARIS_DB_URL from .env.cloud, exiting with a clear error if absent."""
    env_path = ROOT / ".env.cloud"
    if not env_path.exists():
        sys.exit(
            "ERROR: .env.cloud not found at repo root.\n"
            "Create it from the template:\n"
            "    Copy-Item .env.cloud.example .env.cloud\n"
            "    notepad .env.cloud\n"
            "Paste your rewritten Neon URL after ARIS_DB_URL=  (see the template "
            "for the postgresql+psycopg:// + ?sslmode=require rewrite)."
        )
    values = dotenv_values(env_path)
    url = values.get("ARIS_DB_URL", "").strip()
    if not url or "USER:PASSWORD" in url:
        sys.exit(
            "ERROR: ARIS_DB_URL in .env.cloud still holds the placeholder.\n"
            "Open .env.cloud and paste your real, rewritten Neon URL after the `=`."
        )
    return url


def _check_connection(url: str) -> None:
    from sqlalchemy import create_engine

    print("[1/4] verifying Neon connection ...", flush=True)
    create_engine(url).connect().close()
    print("       ok")


def _apply_sql_file(url: str, path: Path) -> int:
    """Execute semicolon-delimited statements from one SQL file; return count."""
    from sqlalchemy import create_engine, text

    sql = path.read_text(encoding="utf-8")
    stmts = [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]
    engine = create_engine(url)
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
    return len(stmts)


def _apply_schema(url: str) -> None:
    print("[2/4] applying db/schema.sql + migrations ...", flush=True)
    for path in _SCHEMA_FILES:
        if not path.exists():
            sys.exit(f"ERROR: missing SQL file: {path}")
        n = _apply_sql_file(url, path)
        print(f"       {path.relative_to(ROOT)}: applied {n} statements")


def _ingest_2024() -> None:
    print("[3/4] ingesting 2024 season (this takes 5-10 min) ...", flush=True)
    import fastf1

    from aris.io.ingest import ingest_session

    cache = ROOT / "fastf1_cache"
    cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache))

    schedule = fastf1.get_event_schedule(2024, include_testing=False)
    ok = failed = total_laps = 0
    for _, event in schedule.iterrows():
        round_no = int(event["RoundNumber"])
        name = str(event["EventName"])
        try:
            counts = ingest_session(2024, round_no, "R")
        except Exception as exc:
            print(f"       [fail] 2024 R{round_no:<2} {name}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        ok += 1
        total_laps += counts["laps"]
        print(f"       [ok]   2024 R{round_no:<2} {name}: +{counts['laps']} laps")
    print(f"       season 2024: {ok} ingested, {failed} failed, +{total_laps} laps total")


def _sanity_counts() -> None:
    from sqlalchemy import text

    from aris.io import db

    print("[4/4] final row counts on Neon ...", flush=True)
    with db.engine().connect() as conn:
        sessions = conn.execute(text("SELECT count(*) FROM sessions")).scalar()
        drivers = conn.execute(text("SELECT count(*) FROM drivers")).scalar()
        laps = conn.execute(text("SELECT count(*) FROM laps")).scalar()
        weather = conn.execute(text("SELECT count(*) FROM session_weather")).scalar()
        results = conn.execute(text("SELECT count(*) FROM session_results")).scalar()
    print(
        f"       sessions={sessions} drivers={drivers} laps={laps} "
        f"weather={weather} results={results}"
    )
    print()
    print("Done. Next: deploy on Streamlit Cloud and paste ARIS_DB_URL into Secrets.")
    print("See DEPLOY.md Step 3 for the exact form fields.")


def main() -> int:
    url = _load_cloud_env()
    os.environ["ARIS_DB_URL"] = url  # picked up by aris.io.db.engine() via lru_cache

    _check_connection(url)
    _apply_schema(url)
    _ingest_2024()
    _sanity_counts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
