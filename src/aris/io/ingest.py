"""Idempotent FastF1 -> Postgres ingest (Phase 2, Week 3 Days 3-4).

`ingest_session(year, event, session_type)` pulls one session from FastF1 and
upserts it into `sessions` / `drivers` / `laps`; passing `include_telemetry=True`
also populates the per-sample `telemetry` table (Day 4 — used to validate the
schema on one race, not for bulk season population). The whole session ingests
inside a single transaction — if any table's insert fails, the entire session
rolls back, so the database never holds a half-ingested race.

Idempotency is by natural key. Every `INSERT` is `ON CONFLICT (<natural key>)
DO NOTHING`, so re-running the same `(year, round_no, session_type)` adds zero
rows. `DO NOTHING` (not `DO UPDATE`) is the right call: a finished race is
immutable — a recorded lap time never changes — so there is nothing to refresh.

The `import aris` requests/forward-ref shim from Week 2 is applied by
`aris/__init__.py`, which Python runs before this module's body — so FastF1,
imported lazily inside `_load_session`, always sees the patched `requests`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

from aris.io.db import engine
from aris.physics.stint import detect_stints

# ingest.py is src/aris/io/ingest.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _REPO_ROOT / "fastf1_cache"

# The eight values the sessions.session_type CHECK constraint accepts.
_VALID_SESSION_TYPES = frozenset({"FP1", "FP2", "FP3", "Q", "SQ", "SS", "R", "SR"})


# --- NaN-safe scalar coercions (pandas NaN/NaT -> SQL NULL, numpy -> native) ---


def _num(value: object) -> float | None:
    """A pandas float/NaN -> a native float, or None."""
    return None if pd.isna(value) else float(value)


def _int(value: object) -> int | None:
    """A pandas float/NaN -> a native int, or None."""
    return None if pd.isna(value) else int(value)


def _str(value: object) -> str | None:
    """Any value/NaN -> a native str, or None."""
    return None if pd.isna(value) else str(value)


def _secs(td: object) -> float | None:
    """A pandas Timedelta/NaT -> total seconds as a float, or None."""
    return None if pd.isna(td) else float(td.total_seconds())


def _clean_gear(value: object) -> int | None:
    """Gear as 1..8, else None — the telemetry-cleaning rule at the ingest boundary.

    FastF1 emits occasional glitched gear values (47, 17, 75 were seen in the
    Bahrain 2024 R import — an F1 car has eight forward gears), so anything
    outside 1..8 is nulled here rather than stored as impossible data.
    """
    g = _int(value)
    return g if g is not None and 1 <= g <= 8 else None


# --- FastF1 load ---------------------------------------------------------------


def _load_session(
    year: int,
    event: int | str,
    session_type: str,
    *,
    with_telemetry: bool = False,
    with_weather: bool = True,
):
    """Load one FastF1 session from the repo-local cache (telemetry optional)."""
    import fastf1  # lazy: keeps `import aris.io.ingest` cheap; shim already applied.

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(_CACHE_DIR))
    sess = fastf1.get_session(year, event, session_type)
    sess.load(
        laps=True,
        telemetry=with_telemetry,
        weather=with_weather,
        messages=False,
    )
    return sess


# --- row builders --------------------------------------------------------------


def _driver_rows(sess, year: int) -> list[dict]:
    """One row per driver that appears in the session's laps."""
    lookup: dict[str, tuple[str, str | None]] = {}
    for _, r in sess.results.iterrows():
        lookup[str(r["Abbreviation"])] = (str(r["FullName"]), _str(r["TeamName"]))

    rows: list[dict] = []
    for code in sorted(sess.laps["Driver"].dropna().unique()):
        full_name, team = lookup.get(code, (code, None))
        rows.append({"code": code, "year": year, "full_name": full_name, "team": team})
    return rows


def _lap_rows(enriched: pd.DataFrame, session_id: int, code_to_id: dict[str, int]) -> list[dict]:
    """Translate a `detect_stints`-enriched laps frame into `laps` table rows.

    `stint` is the compound-change-cumsum `StintId` from `aris.physics.stint`,
    not FastF1's native `Stint` column — Day 4's SQL baseline cross-check
    partitions on it and must reproduce Week 2's pandas baseline exactly.
    """
    rows: list[dict] = []
    for rec in enriched.itertuples(index=False):
        driver_id = code_to_id.get(rec.Driver)
        if driver_id is None or pd.isna(rec.LapNumber):
            continue  # a lap with no resolvable driver or no lap number is unusable
        rows.append(
            {
                "session_id": session_id,
                "driver_id": driver_id,
                "lap_number": int(rec.LapNumber),
                "lap_time_s": _num(rec.LapTimeS),
                "compound": _str(rec.Compound),
                "tyre_life": _int(rec.TyreLife),
                "stint": int(rec.StintId),
                "sector_1_s": _secs(rec.Sector1Time),
                "sector_2_s": _secs(rec.Sector2Time),
                "sector_3_s": _secs(rec.Sector3Time),
                "track_status": _str(rec.TrackStatus),
                "pit_in": bool(pd.notna(rec.PitInTime)),
                "pit_out": bool(pd.notna(rec.PitOutTime)),
            }
        )
    return rows


# --- upserts -------------------------------------------------------------------

_INSERT_SESSION = text(
    """
    INSERT INTO sessions (year, round_no, country, session_type, date)
    VALUES (:year, :round_no, :country, :session_type, :date)
    ON CONFLICT (year, round_no, session_type) DO NOTHING
    RETURNING session_id
    """
)

_INSERT_DRIVER = text(
    """
    INSERT INTO drivers (code, year, full_name, team)
    VALUES (:code, :year, :full_name, :team)
    ON CONFLICT (code, year) DO NOTHING
    """
)

_INSERT_LAP = text(
    """
    INSERT INTO laps (
        session_id, driver_id, lap_number, lap_time_s, compound, tyre_life,
        stint, sector_1_s, sector_2_s, sector_3_s, track_status, pit_in, pit_out
    )
    VALUES (
        :session_id, :driver_id, :lap_number, :lap_time_s, :compound, :tyre_life,
        :stint, :sector_1_s, :sector_2_s, :sector_3_s, :track_status, :pit_in, :pit_out
    )
    ON CONFLICT (session_id, driver_id, lap_number) DO NOTHING
    """
)

_INSERT_TELEMETRY = text(
    """
    INSERT INTO telemetry (
        session_id, driver_id, lap_number, sample_idx,
        speed, throttle, brake, gear, drs, rpm, x, y, z
    )
    VALUES (
        :session_id, :driver_id, :lap_number, :sample_idx,
        :speed, :throttle, :brake, :gear, :drs, :rpm, :x, :y, :z
    )
    ON CONFLICT (session_id, driver_id, lap_number, sample_idx)
    DO UPDATE SET gear = EXCLUDED.gear
    """
)
# `gear` is the one column that does DO UPDATE rather than DO NOTHING: a finished
# race is immutable, but the Week 4 gear-cleaning rule is a data-quality fix that
# must be able to overwrite gears stored before the rule existed. Re-running the
# telemetry ingest therefore nulls the ~20 glitched-gear rows in place; every
# other channel is left exactly as first captured.

# Telemetry is ~500k rows per race — flush in chunks so a single executemany
# never has to hold the whole race's samples in one bind list.
_TELEMETRY_BATCH = 20_000


def _upsert_session(
    conn: Connection, year: int, round_no: int, country: str, session_type: str, date
) -> tuple[int, int]:
    """Upsert the session row; return (session_id, rows_inserted)."""
    params = {
        "year": year,
        "round_no": round_no,
        "country": country,
        "session_type": session_type,
        "date": date,
    }
    inserted = conn.execute(_INSERT_SESSION, params).fetchone()
    if inserted is not None:
        return int(inserted[0]), 1
    # Already present (conflict) — RETURNING gave nothing, so look the id up.
    sid = conn.execute(
        text(
            "SELECT session_id FROM sessions "
            "WHERE year = :year AND round_no = :round_no AND session_type = :session_type"
        ),
        params,
    ).scalar_one()
    return int(sid), 0


def _upsert_drivers(conn: Connection, year: int, rows: list[dict]) -> tuple[dict[str, int], int]:
    """Upsert driver rows; return (code -> driver_id map, rows_inserted)."""
    before = conn.execute(
        text("SELECT count(*) FROM drivers WHERE year = :year"), {"year": year}
    ).scalar_one()
    if rows:
        conn.execute(_INSERT_DRIVER, rows)
    after = conn.execute(
        text("SELECT count(*) FROM drivers WHERE year = :year"), {"year": year}
    ).scalar_one()
    code_to_id = {
        code: int(did)
        for code, did in conn.execute(
            text("SELECT code, driver_id FROM drivers WHERE year = :year"), {"year": year}
        ).all()
    }
    return code_to_id, after - before


def _upsert_laps(conn: Connection, session_id: int, rows: list[dict]) -> int:
    """Upsert lap rows; return rows_inserted (after - before, conflict-skip aware)."""
    before = conn.execute(
        text("SELECT count(*) FROM laps WHERE session_id = :sid"), {"sid": session_id}
    ).scalar_one()
    if rows:
        conn.execute(_INSERT_LAP, rows)
    after = conn.execute(
        text("SELECT count(*) FROM laps WHERE session_id = :sid"), {"sid": session_id}
    ).scalar_one()
    return after - before


def _telemetry_rows_for_lap(lap, session_id: int, driver_id: int) -> list[dict]:
    """Per-sample telemetry rows for one lap; [] when the lap has no telemetry."""
    if pd.isna(lap["LapNumber"]):
        return []
    try:
        tel = lap.get_telemetry()
    except Exception:  # a single lap with missing telemetry must not abort the race
        return []
    if tel is None or tel.empty:
        return []

    lap_number = int(lap["LapNumber"])
    rows: list[dict] = []
    for sample_idx, t in enumerate(tel.itertuples(index=False)):
        rows.append(
            {
                "session_id": session_id,
                "driver_id": driver_id,
                "lap_number": lap_number,
                "sample_idx": sample_idx,
                "speed": _num(t.Speed),
                "throttle": _num(t.Throttle),
                "brake": None if pd.isna(t.Brake) else bool(t.Brake),
                "gear": _clean_gear(t.nGear),
                "drs": _int(t.DRS),
                "rpm": _num(t.RPM),
                "x": _num(t.X),
                "y": _num(t.Y),
                "z": _num(t.Z),
            }
        )
    return rows


_INSERT_WEATHER = text(
    """
    INSERT INTO session_weather (session_id, air_temp_c, track_temp_c, humidity_pct, rainfall)
    VALUES (:session_id, :air_temp_c, :track_temp_c, :humidity_pct, :rainfall)
    ON CONFLICT (session_id) DO UPDATE SET
        air_temp_c = EXCLUDED.air_temp_c,
        track_temp_c = EXCLUDED.track_temp_c,
        humidity_pct = EXCLUDED.humidity_pct,
        rainfall = EXCLUDED.rainfall
    """
)

_INSERT_RESULT = text(
    """
    INSERT INTO session_results (session_id, driver_id, grid_pos, finish_pos, points)
    VALUES (:session_id, :driver_id, :grid_pos, :finish_pos, :points)
    ON CONFLICT (session_id, driver_id) DO UPDATE SET
        grid_pos = EXCLUDED.grid_pos,
        finish_pos = EXCLUDED.finish_pos,
        points = EXCLUDED.points
    """
)


def _weather_summary(sess) -> dict | None:
    """Median session weather from FastF1 weather dataframe."""
    weather = getattr(sess, "weather_data", None)
    if weather is None or weather.empty:
        return None
    rainfall = bool(weather.get("Rainfall", pd.Series([False])).any())
    return {
        "air_temp_c": _num(weather["AirTemp"].median()) if "AirTemp" in weather else None,
        "track_temp_c": _num(weather["TrackTemp"].median()) if "TrackTemp" in weather else None,
        "humidity_pct": _num(weather["Humidity"].median()) if "Humidity" in weather else None,
        "rainfall": rainfall,
    }


def _result_rows(sess, session_id: int, code_to_id: dict[str, int]) -> list[dict]:
    """Grid/finish positions from FastF1 session results."""
    rows: list[dict] = []
    for _, r in sess.results.iterrows():
        code = str(r.get("Abbreviation", ""))
        driver_id = code_to_id.get(code)
        if driver_id is None:
            continue
        rows.append(
            {
                "session_id": session_id,
                "driver_id": driver_id,
                "grid_pos": _int(r.get("GridPosition")),
                "finish_pos": _int(r.get("Position")),
                "points": _num(r.get("Points")),
            }
        )
    return rows


def _table_exists(conn: Connection, table: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT to_regclass(:name) IS NOT NULL"),
            {"name": f"public.{table}"},
        ).scalar_one()
    )


def _upsert_weather(conn: Connection, session_id: int, summary: dict | None) -> int:
    """Upsert weather; return 1 only when a new row was inserted (not updated)."""
    if summary is None or not _table_exists(conn, "session_weather"):
        return 0
    before = conn.execute(
        text("SELECT count(*) FROM session_weather WHERE session_id = :sid"),
        {"sid": session_id},
    ).scalar_one()
    conn.execute(_INSERT_WEATHER, {"session_id": session_id, **summary})
    after = conn.execute(
        text("SELECT count(*) FROM session_weather WHERE session_id = :sid"),
        {"sid": session_id},
    ).scalar_one()
    return after - before


def _upsert_results(conn: Connection, rows: list[dict]) -> int:
    """Upsert results; return count of newly inserted rows (updates do not count)."""
    if not rows or not _table_exists(conn, "session_results"):
        return 0
    session_id = rows[0]["session_id"]
    before = conn.execute(
        text("SELECT count(*) FROM session_results WHERE session_id = :sid"),
        {"sid": session_id},
    ).scalar_one()
    conn.execute(_INSERT_RESULT, rows)
    after = conn.execute(
        text("SELECT count(*) FROM session_results WHERE session_id = :sid"),
        {"sid": session_id},
    ).scalar_one()
    return after - before


def _upsert_telemetry(conn: Connection, session_id: int, code_to_id: dict[str, int], sess) -> int:
    """Upsert every lap's telemetry samples; return rows_inserted.

    Idempotent on the `telemetry` composite PK `(session_id, driver_id,
    lap_number, sample_idx)` — re-running inserts nothing.
    """
    before = conn.execute(
        text("SELECT count(*) FROM telemetry WHERE session_id = :sid"), {"sid": session_id}
    ).scalar_one()

    batch: list[dict] = []
    for _, lap in sess.laps.iterlaps():
        driver_id = code_to_id.get(lap["Driver"])
        if driver_id is None:
            continue
        batch.extend(_telemetry_rows_for_lap(lap, session_id, driver_id))
        if len(batch) >= _TELEMETRY_BATCH:
            conn.execute(_INSERT_TELEMETRY, batch)
            batch.clear()
    if batch:
        conn.execute(_INSERT_TELEMETRY, batch)

    after = conn.execute(
        text("SELECT count(*) FROM telemetry WHERE session_id = :sid"), {"sid": session_id}
    ).scalar_one()
    return after - before


# --- public API ----------------------------------------------------------------


def ingest_session(
    year: int, event: int | str, session_type: str, *, include_telemetry: bool = False
) -> dict[str, int]:
    """Ingest one FastF1 session into Postgres; return per-table rows inserted.

    `event` is a round number (``1``) or an event name (``"Bahrain"``) — both
    are accepted by FastF1; the real round number is read back from the loaded
    event and stored. Re-running with the same arguments inserts nothing and
    returns all-zero counts.

    With `include_telemetry=True` the per-sample `telemetry` table is populated
    too and the returned dict carries a fourth `"telemetry"` key; the default
    (laps-only) ingest returns just `sessions` / `drivers` / `laps`.
    """
    session_type = session_type.upper()
    if session_type not in _VALID_SESSION_TYPES:
        raise ValueError(
            f"session_type {session_type!r} not one of {sorted(_VALID_SESSION_TYPES)}"
        )

    sess = _load_session(
        year, event, session_type, with_telemetry=include_telemetry, with_weather=True
    )
    round_no = int(sess.event["RoundNumber"])
    country = str(sess.event["Country"])
    raw_date = sess.date
    date = None if raw_date is None or pd.isna(raw_date) else pd.Timestamp(raw_date).to_pydatetime()

    enriched = detect_stints(sess.laps)
    driver_rows = _driver_rows(sess, year)
    weather_summary = _weather_summary(sess)

    # One transaction for the whole session: engine().begin() commits on a
    # clean exit and rolls back on any exception — never a half-ingested race.
    with engine().begin() as conn:
        session_id, n_sessions = _upsert_session(
            conn, year, round_no, country, session_type, date
        )
        code_to_id, n_drivers = _upsert_drivers(conn, year, driver_rows)
        lap_rows = _lap_rows(enriched, session_id, code_to_id)
        n_laps = _upsert_laps(conn, session_id, lap_rows)
        counts = {"sessions": n_sessions, "drivers": n_drivers, "laps": n_laps}
        counts["weather"] = _upsert_weather(conn, session_id, weather_summary)
        counts["results"] = _upsert_results(
            conn, _result_rows(sess, session_id, code_to_id)
        )
        if include_telemetry:
            counts["telemetry"] = _upsert_telemetry(conn, session_id, code_to_id, sess)

    return counts
