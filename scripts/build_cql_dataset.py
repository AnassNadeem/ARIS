#!/usr/bin/env python
"""Build the offline CQL transition dataset from REFERENCE_RACES.

In-laps (PitInTime) are PIT_* actions. Out-laps (PitOutTime) are dropped.
Wet/INTER laps and TrackStatus '5' are dropped. SC/VSC (4/6/7) are kept.
P1–P10 classified finishers only. Reward is finish_pos with MC return.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.models.residual import REFERENCE_RACES  # noqa: E402

FASTF1_CACHE_PATH = ROOT / "fastf1_cache"

ACTION_NAMES = {
    0: "STAY_OUT",
    1: "SOFT",
    2: "MEDIUM",
    3: "HARD",
    4: "INTERMEDIATE",
    5: "WET",
}
COMPOUND_TO_ACTION = {
    "SOFT": 1,
    "MEDIUM": 2,
    "HARD": 3,
    "INTERMEDIATE": 4,
    "INTER": 4,
    "WET": 5,
}
# Pre-2019 FastF1 names. Must map onto PIT_* (D1) — unknown-compound
# in-laps must not collapse to STAY_OUT.
_VINTAGE_COMPOUND = {
    "HYPERSOFT": "SOFT",
    "ULTRASOFT": "SOFT",
    "SUPERSOFT": "SOFT",
    "SUPERHARD": "HARD",
    "C5": "SOFT",
    "C4": "SOFT",
    "C3": "MEDIUM",
    "C2": "HARD",
    "C1": "HARD",
}
WET_COMPOUNDS = frozenset({"INTERMEDIATE", "INTER", "WET"})


def _canonical_compound(raw: object) -> str:
    key = str(raw or "").strip().upper()
    return _VINTAGE_COMPOUND.get(key, key)
COLUMN_ORDER = [
    "session_key",
    "race_year",
    "round_number",
    "driver_code",
    "lap_number",
    "compound",
    "tyre_life",
    "lag1_s",
    "lag2_s",
    "roll3_s",
    "gap_ahead",
    "gap_h1",
    "gap_h2",
    "gap_h3",
    "fuel_kg",
    "laps_remaining",
    "track_status",
    "rainfall",
    "position",
    "stint",
    "action",
    "return_g",
]


def _norm_drv(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value).strip()


def _lap_seconds(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cumulative_by_lap(all_laps: pd.DataFrame) -> dict[int, dict[str, float]]:
    """ref_lap -> {driver_num: cumulative time through that lap}."""
    out: dict[int, dict[str, float]] = {}
    if all_laps is None or all_laps.empty or "LapNumber" not in all_laps.columns:
        return out
    running: dict[str, float] = {}
    max_lap = int(all_laps["LapNumber"].max())
    for lap_n in range(1, max_lap + 1):
        slice_ = all_laps[all_laps["LapNumber"] == lap_n]
        for _, row in slice_.iterrows():
            drv = _norm_drv(row.get("DriverNumber", row.get("Driver")))
            if not drv:
                continue
            secs = _lap_seconds(row.get("LapTime"))
            if secs is None:
                continue
            running[drv] = running.get(drv, 0.0) + secs
        out[lap_n] = dict(running)
    return out


def _estimate_gap_ahead(
    all_laps,
    driver_num,
    focus_lap,
    ref_lap,
    *,
    _table: dict[int, dict[str, float]] | None = None,
) -> float:
    """Approximate gap to car ahead using cumulative lap times.

    Sort drivers by cumulative time through ref_lap. Gap is this driver's
    cumulative time minus the car ahead's. P1 / unknown → 22.0. Capped [0, 22].
    """
    del focus_lap
    table = _table if _table is not None else _cumulative_by_lap(all_laps)
    try:
        ref = int(ref_lap)
    except (TypeError, ValueError):
        return 22.0
    if ref < 1 or ref not in table:
        return 22.0
    times = table[ref]
    drv = _norm_drv(driver_num)
    if drv not in times:
        return 22.0
    ranked = sorted(times.items(), key=lambda kv: kv[1])
    pos = next((i for i, (d, _) in enumerate(ranked) if d == drv), None)
    if pos is None or pos == 0:
        return 22.0
    # Driver time − car-ahead time (positive when behind). Spec shorthand
    # subtracted the other way; that would clamp every gap to 0.
    gap = times[drv] - ranked[pos - 1][1]
    return float(min(22.0, max(0.0, gap)))


def _get_rainfall(weather_data, lap_row) -> bool:
    """Nearest weather sample to LapStartDate. Empty / no match → False."""
    if weather_data is None:
        return False
    try:
        if getattr(weather_data, "empty", True):
            return False
    except Exception:
        return False
    if "Rainfall" not in weather_data.columns:
        return False

    target_date = None
    if lap_row is not None:
        try:
            raw = lap_row["LapStartDate"] if "LapStartDate" in lap_row.index else None
        except Exception:
            raw = None
        if raw is not None and pd.notna(raw):
            target_date = pd.Timestamp(raw)

    if target_date is not None and "Date" in weather_data.columns:
        dates = pd.to_datetime(weather_data["Date"], errors="coerce")
        valid = dates.dropna()
        if not valid.empty:
            idx = (valid - target_date).abs().idxmin()
            return bool(weather_data.loc[idx, "Rainfall"])

    target_time = None
    if lap_row is not None:
        try:
            raw_t = lap_row["LapStartTime"] if "LapStartTime" in lap_row.index else None
        except Exception:
            raw_t = None
        target_time = _lap_seconds(raw_t)

    if target_time is not None and "Time" in weather_data.columns:
        times = weather_data["Time"].map(_lap_seconds)
        valid = times.dropna()
        if not valid.empty:
            idx = (valid - target_time).abs().idxmin()
            return bool(weather_data.loc[idx, "Rainfall"])

    series = weather_data["Rainfall"].fillna(False)
    if series.empty:
        return False
    return bool(series.iloc[-1])


def _get_position(
    all_laps,
    driver_num,
    lap_n,
    *,
    _table: dict[int, dict[str, float]] | None = None,
) -> int:
    """Position at end of lap_n from cumulative times. Default 10."""
    table = _table if _table is not None else _cumulative_by_lap(all_laps)
    try:
        lap = int(lap_n)
    except (TypeError, ValueError):
        return 10
    times = table.get(lap)
    if not times:
        return 10
    ranked = sorted(times.items(), key=lambda kv: kv[1])
    drv = _norm_drv(driver_num)
    for i, (d, _) in enumerate(ranked, start=1):
        if d == drv:
            return int(min(20, max(1, i)))
    return 10


def _pos_le_10(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = str(value).strip()
    if text.isdigit():
        return int(text) <= 10
    try:
        pos = int(float(text))
    except (TypeError, ValueError):
        return False
    return 1 <= pos <= 10


def _classified_p1_p10(results: pd.DataFrame) -> pd.DataFrame:
    if results is None or getattr(results, "empty", True):
        return pd.DataFrame()
    if "ClassifiedPosition" in results.columns:
        mask = results["ClassifiedPosition"].apply(_pos_le_10)
        if bool(mask.any()):
            return results[mask].copy()
    if "Position" in results.columns:
        # Ergast/Jolpica can be down; FastF1 still fills timing Position.
        return results[results["Position"].apply(_pos_le_10)].copy()
    return pd.DataFrame()


def _pick_driver_laps(laps: pd.DataFrame, driver_number: Any) -> pd.DataFrame:
    drv = _norm_drv(driver_number)
    if laps is None or laps.empty:
        return laps
    try:
        picked = laps.pick_drivers(driver_number)
        if picked is not None and not picked.empty:
            return picked
    except Exception:
        pass
    try:
        picked = laps.pick_driver(driver_number)
        if picked is not None and not picked.empty:
            return picked
    except Exception:
        pass
    if "DriverNumber" in laps.columns:
        hit = laps[laps["DriverNumber"].map(_norm_drv) == drv]
        if not hit.empty:
            return hit
    if "Driver" in laps.columns:
        hit = laps[laps["Driver"].astype(str) == str(driver_number)]
        if not hit.empty:
            return hit
    return laps.iloc[0:0]


def _load_session(year: int, gp: str, round_no: int = 0):
    import time

    from fastf1.exceptions import RateLimitExceededError

    from aris.io.fastf1_session import load_race_session

    attempts = 0
    while True:
        attempts += 1
        try:
            return load_race_session(
                year,
                gp,
                laps=True,
                weather=True,
                telemetry=False,
                cache_dir=FASTF1_CACHE_PATH,
                round_no=round_no,
            )
        except RateLimitExceededError:
            wait_s = 120 * attempts
            print(
                f"  rate-limited on {year} {gp}; sleeping {wait_s}s "
                f"(attempt {attempts})",
                flush=True,
            )
            time.sleep(wait_s)
            if attempts >= 6:
                raise


def _session_meta(session, year: int) -> tuple[str, int, int]:
    event = session.event
    try:
        round_no = int(event["RoundNumber"])
    except Exception:
        try:
            round_no = int(event.RoundNumber)
        except Exception:
            round_no = 0
    session_key = f"{year}_{round_no:02d}_R"
    try:
        total = int(session.total_laps) if session.total_laps else 0
    except Exception:
        total = 0
    if total <= 0:
        try:
            laps = session.laps
            if laps is not None and not laps.empty:
                total = int(laps["LapNumber"].max())
        except Exception:
            total = 0
    return session_key, round_no, total


def _process_session(
    session,
    year: int,
    gamma: float,
) -> tuple[list[dict[str, Any]], int]:
    """Return (filtered rows, count if wet/red were not filtered)."""
    session_key, round_no, total_laps = _session_meta(session, year)
    try:
        all_laps = session.laps
    except Exception:
        return [], 0
    if total_laps < 3 or all_laps is None or all_laps.empty:
        return [], 0

    try:
        results = session.results
    except Exception:
        results = pd.DataFrame()
    classified = _classified_p1_p10(results)
    if classified.empty:
        return [], 0

    table = _cumulative_by_lap(all_laps)
    try:
        weather = getattr(session, "weather_data", None)
    except Exception:
        weather = None
    rows: list[dict[str, Any]] = []
    n_unfiltered = 0

    for _, res in classified.iterrows():
        driver_number = res.get("DriverNumber")
        driver_code = str(res.get("Abbreviation") or res.get("Driver") or "").strip()
        finish_raw = res.get("ClassifiedPosition")
        if not _pos_le_10(finish_raw):
            finish_raw = res.get("Position")
        try:
            finish_pos = int(float(finish_raw))
        except (TypeError, ValueError):
            continue
        if not driver_code or finish_pos < 1:
            continue

        laps = _pick_driver_laps(all_laps, driver_number)
        if laps is None or laps.empty:
            continue

        driver_rows: list[dict[str, Any]] = []
        for lap_n in range(2, total_laps):
            lap = laps[laps["LapNumber"] == lap_n]
            if lap.empty:
                continue
            rec = lap.iloc[0]
            pit_out = rec.get("PitOutTime")
            if pd.notna(pit_out):
                continue

            prior_laps = laps[laps["LapNumber"] < lap_n]
            if len(prior_laps) < 2:
                continue
            lag1 = prior_laps.iloc[-1]["LapTime"]
            lag2 = prior_laps.iloc[-2]["LapTime"]
            lag1_s = _lap_seconds(lag1)
            lag2_s = _lap_seconds(lag2)
            if lag1_s is None or lag2_s is None:
                continue

            n_unfiltered += 1

            track_status = str(rec.get("TrackStatus") if pd.notna(rec.get("TrackStatus")) else "")
            if "5" in track_status:
                continue
            compound = _canonical_compound(rec.get("Compound"))
            if compound in WET_COMPOUNDS:
                continue

            is_pit = pd.notna(rec.get("PitInTime"))
            if is_pit:
                # In-laps stay PIT_* even if the following stint is missing (DNF).
                next_lap = laps[laps["LapNumber"] == lap_n + 1]
                if next_lap.empty:
                    action = 3
                else:
                    next_compound = _canonical_compound(next_lap.iloc[0].get("Compound"))
                    action = COMPOUND_TO_ACTION.get(next_compound, 3)
            else:
                action = 0

            roll3_laps = prior_laps.tail(3)
            roll3_times = [
                t
                for t in (_lap_seconds(v) for v in roll3_laps["LapTime"].tolist())
                if t is not None
            ]
            roll3 = sum(roll3_times) / len(roll3_times) if roll3_times else lag1_s

            tyre_life = int(rec["TyreLife"]) if pd.notna(rec.get("TyreLife")) else 1
            stint = int(rec["Stint"]) if pd.notna(rec.get("Stint")) else 1
            gap_ahead = _estimate_gap_ahead(
                all_laps, driver_number, lap_n, lap_n, _table=table
            )
            gap_h1 = _estimate_gap_ahead(
                all_laps, driver_number, lap_n, lap_n - 1, _table=table
            )
            gap_h2 = _estimate_gap_ahead(
                all_laps, driver_number, lap_n, lap_n - 2, _table=table
            )
            gap_h3 = _estimate_gap_ahead(
                all_laps, driver_number, lap_n, lap_n - 3, _table=table
            )
            fuel_kg = max(0.0, 110.0 - 1.7 * (lap_n - 1))
            laps_remaining = total_laps - lap_n
            rainfall = _get_rainfall(weather, rec)
            position = _get_position(
                all_laps, driver_number, lap_n, _table=table
            )

            driver_rows.append(
                {
                    "session_key": session_key,
                    "race_year": int(year),
                    "round_number": int(round_no),
                    "driver_code": driver_code,
                    "lap_number": int(lap_n),
                    "compound": compound,
                    "tyre_life": int(tyre_life),
                    "lag1_s": float(lag1_s),
                    "lag2_s": float(lag2_s),
                    "roll3_s": float(roll3),
                    "gap_ahead": float(gap_ahead),
                    "gap_h1": float(gap_h1),
                    "gap_h2": float(gap_h2),
                    "gap_h3": float(gap_h3),
                    "fuel_kg": float(fuel_kg),
                    "laps_remaining": int(laps_remaining),
                    "track_status": track_status,
                    "rainfall": bool(rainfall),
                    "position": int(position),
                    "stint": int(stint),
                    "action": int(action),
                    "return_g": 0.0,
                    "finish_pos": int(finish_pos),
                    "total_laps": int(total_laps),
                }
            )

        for row in driver_rows:
            t = row["lap_number"]
            t_end = row["total_laps"]
            row["return_g"] = float((gamma ** (t_end - t)) * row["finish_pos"])
            del row["finish_pos"]
            del row["total_laps"]
            rows.append(row)

    return rows, n_unfiltered


def _print_summary(
    rows: list[dict[str, Any]],
    skipped: list[str],
    n_unfiltered: int,
) -> None:
    n = len(rows)
    actions = Counter(int(r["action"]) for r in rows)
    years = Counter(int(r["race_year"]) for r in rows)
    print(f"Total transitions: {n}", flush=True)
    action_bits = [
        f"{k}: {actions.get(k, 0)} ({ACTION_NAMES[k]})" for k in range(6)
    ]
    print(f"Action distribution: {{{', '.join(action_bits)}}}", flush=True)
    year_bits = [f"{y}: {years[y]}" for y in sorted(years)]
    print(f"Year distribution: {{{', '.join(year_bits)}}}", flush=True)
    print(f"Sessions skipped: {len(skipped)}", flush=True)
    for reason in skipped:
        print(f"  - {reason}", flush=True)
    print(
        f"Estimated training rows if wet/red not filtered: {n_unfiltered}",
        flush=True,
    )


def build_dataset(
    years: list[int],
    *,
    gamma: float = 0.95,
) -> tuple[list[dict[str, Any]], list[str], int]:
    wanted = set(int(y) for y in years)
    races = [(y, gp) for y, gp in REFERENCE_RACES if y in wanted]
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    n_unfiltered = 0
    n = len(races)
    print(f"Building CQL dataset from {n} REFERENCE_RACES in {sorted(wanted)}", flush=True)
    for i, (year, gp) in enumerate(races, start=1):
        label = f"{year} {gp}"
        try:
            year_races = [(y, name) for y, name in REFERENCE_RACES if y == year]
            round_no = year_races.index((year, gp)) + 1
            session = _load_session(year, gp, round_no=round_no)
            race_rows, race_m = _process_session(session, year, gamma)
            rows.extend(race_rows)
            n_unfiltered += race_m
            print(f"[{i}/{n}] OK {label}: {len(race_rows)} transitions", flush=True)
        except Exception as exc:  # noqa: BLE001 — continue corpus; never crash
            skipped.append(f"{label} ({type(exc).__name__}: {exc})")
            print(f"[{i}/{n}] SKIP {label}: {exc}", flush=True)
    return rows, skipped, n_unfiltered


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the CQL offline dataset")
    parser.add_argument("--years", type=int, nargs="+", required=True)
    parser.add_argument("--gamma", type=float, default=0.95)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "cql_dataset.parquet",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary only; do not write a parquet file",
    )
    args = parser.parse_args()

    rows, skipped, n_unfiltered = build_dataset(args.years, gamma=args.gamma)
    _print_summary(rows, skipped, n_unfiltered)

    if args.dry_run:
        print("dry-run: no file written", flush=True)
        return 0

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=COLUMN_ORDER)
    else:
        df = df[COLUMN_ORDER]
        df["rainfall"] = df["rainfall"].astype(bool)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.output, index=False)
    print(f"Wrote {len(df)} rows to {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
