"""Gap-to-nearest-car from cumulative lap times.

G3.3 computed this for the pace-management confound. G4 reuses the same
construction — do not invent a second gap definition.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from aris.physics.tires import normalize_compound

_SC_CODES = ("4", "6", "7")


def gaps_at_completed_laps(
    laps: pd.DataFrame,
    *,
    driver_col: str = "driver_id",
    lap_col: str = "lap_number",
    time_col: str = "lap_time_s",
    track_status_col: str | None = "track_status",
    pit_col: str | None = None,
    pit_in_col: str | None = "pit_in",
    pit_out_col: str | None = "pit_out",
) -> pd.DataFrame:
    """Per (driver, lap) gap_ahead / gap_behind from cumulative race time.

    Same algorithm as ``scripts/_g3_pace_pressure.py``: at each completed lap,
    sort cars by cumulative lap time and take the adjacent deltas. ``min_nearby_s``
    is min(ahead, behind) among the neighbours that exist (leader has no ahead;
    last has no behind). Laps with fewer than two cars with a finite cumulative
    time are skipped (no gap).
    """
    work = laps.copy()
    if "compound" in work.columns:
        work["compound"] = work["compound"].map(normalize_compound)
    work = work.sort_values([driver_col, lap_col])
    work["_lt"] = pd.to_numeric(work[time_col], errors="coerce")
    work["_cum"] = work.groupby(driver_col, sort=False)["_lt"].cumsum()

    if pit_col and pit_col in work.columns:
        pit_series = work[pit_col].fillna(False).astype(bool)
    else:
        pit_in = (
            work[pit_in_col].fillna(False).astype(bool)
            if pit_in_col and pit_in_col in work.columns
            else pd.Series(False, index=work.index)
        )
        pit_out = (
            work[pit_out_col].fillna(False).astype(bool)
            if pit_out_col and pit_out_col in work.columns
            else pd.Series(False, index=work.index)
        )
        pit_series = pit_in | pit_out
    work["_pit"] = pit_series

    rows: list[dict[str, Any]] = []
    for lap, grp in work.groupby(lap_col, sort=True):
        valid = grp.dropna(subset=["_cum"]).sort_values("_cum")
        if len(valid) < 2:
            continue
        cums = valid["_cum"].to_numpy(dtype=float)
        for i, (_, r) in enumerate(valid.iterrows()):
            ahead = float(cums[i] - cums[i - 1]) if i > 0 else None
            behind = float(cums[i + 1] - cums[i]) if i + 1 < len(cums) else None
            nearby = None
            if ahead is not None or behind is not None:
                parts = [g for g in (ahead, behind) if g is not None]
                nearby = min(parts) if parts else None
            track = ""
            if track_status_col and track_status_col in valid.columns:
                track = str(r.get(track_status_col) or "")
            sc = any(c in track for c in _SC_CODES)
            ahead_driver = valid.iloc[i - 1][driver_col] if i > 0 else None
            behind_driver = (
                valid.iloc[i + 1][driver_col] if i + 1 < len(valid) else None
            )
            row: dict[str, Any] = {
                driver_col: r[driver_col],
                lap_col: int(lap) if pd.notna(lap) else lap,
                "gap_ahead_s": ahead,
                "gap_behind_s": behind,
                "min_nearby_s": nearby,
                "ahead_driver": ahead_driver,
                "behind_driver": behind_driver,
                "pit": bool(r["_pit"]),
                "sc": sc,
                "position": i + 1,
            }
            for extra in ("compound", "stint", "tyre_life", "StintId", "TyreLife", "Compound"):
                if extra in valid.columns:
                    row[extra] = r.get(extra)
            rows.append(row)
    return pd.DataFrame(rows)


def gaps_from_db_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """G3.3 DB schema: driver_id, lap_number, lap_time_s, pit_in/pit_out."""
    return gaps_at_completed_laps(laps)


def gaps_from_fastf1_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """FastF1 / detect_stints schema: Driver, LapNumber, LapTimeS, Pit*Time."""
    work = laps.copy()
    if "LapTimeS" not in work.columns:
        if "LapTime" in work.columns:
            work["LapTimeS"] = pd.to_timedelta(work["LapTime"]).dt.total_seconds()
        else:
            raise ValueError("FastF1 laps need LapTimeS or LapTime")
    pit = pd.Series(False, index=work.index)
    if "PitInTime" in work.columns:
        pit = pit | work["PitInTime"].notna()
    if "PitOutTime" in work.columns:
        pit = pit | work["PitOutTime"].notna()
    work["pit"] = pit
    if "compound" not in work.columns and "Compound" in work.columns:
        work["compound"] = work["Compound"].map(normalize_compound)
    if "stint" not in work.columns and "StintId" in work.columns:
        work["stint"] = work["StintId"]
    if "tyre_life" not in work.columns and "TyreLife" in work.columns:
        work["tyre_life"] = work["TyreLife"]
    return gaps_at_completed_laps(
        work,
        driver_col="Driver",
        lap_col="LapNumber",
        time_col="LapTimeS",
        track_status_col="TrackStatus" if "TrackStatus" in work.columns else None,
        pit_col="pit",
        pit_in_col=None,
        pit_out_col=None,
    )
