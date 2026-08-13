"""Practice and qualifying form summaries."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from aris.io import db


@dataclass
class DriverForm:
    driver_id: int
    code: str
    full_name: str
    team: str | None
    best_soft: float | None = None
    best_medium: float | None = None
    best_hard: float | None = None
    quali_time: float | None = None
    deg_slope: float | None = None


def _best_per_compound(laps: pd.DataFrame) -> dict[str, float]:
    bests: dict[str, float] = {}
    for compound in ("SOFT", "MEDIUM", "HARD"):
        subset = laps[laps["compound"].str.upper() == compound]
        times = subset["lap_time_s"].dropna()
        if not times.empty:
            bests[compound] = float(times.min())
    return bests


def _deg_slope(laps: pd.DataFrame) -> float | None:
    """Linear DegSlope (s/lap of tyre life) via polyfit — not a correlation.

    Earlier versions returned Pearson r, which is unitless and was mislabeled
    ``deg_slope``. Callers expect a slope in seconds per tyre-life lap.
    """
    clean = laps.dropna(subset=["lap_time_s", "tyre_life"])
    if len(clean) < 4:
        return None
    clean = clean.sort_values("tyre_life")
    x = clean["tyre_life"].astype(float).to_numpy()
    y = clean["lap_time_s"].astype(float).to_numpy()
    if float(np.std(x)) == 0.0:
        return None
    slope, _ = np.polyfit(x, y, 1)
    return float(slope) if np.isfinite(slope) else None


def weekend_form(year: int, round_no: int) -> list[DriverForm]:
    """Per-driver FP/Q summary for a weekend."""
    sessions = db.fetch_weekend_sessions(year, round_no)
    if sessions.empty:
        return []

    fp_ids = sessions[
        sessions["session_type"].isin(["FP1", "FP2", "FP3", "S", "SS", "SR"])
    ]["session_id"].tolist()
    # Prefer SQ (sprint quali) as a pace reference when conventional Q is late;
    # still use Q when present.
    q_rows = sessions[sessions["session_type"] == "Q"]
    if q_rows.empty:
        q_rows = sessions[sessions["session_type"].isin(["SQ", "SS"])]
    quali_id = int(q_rows.iloc[0]["session_id"]) if not q_rows.empty else None

    drivers: dict[int, DriverForm] = {}
    for sid in fp_ids:
        all_laps = db.fetch_all_laps(int(sid))
        for driver_id, grp in all_laps.groupby("driver_id"):
            row = grp.iloc[0]
            form = drivers.get(
                int(driver_id),
                DriverForm(
                    driver_id=int(driver_id),
                    code=str(row["code"]),
                    full_name=str(row["full_name"]),
                    team=str(row["team"]) if pd.notna(row.get("team")) else None,
                ),
            )
            bests = _best_per_compound(grp)
            form.best_soft = form.best_soft or bests.get("SOFT")
            form.best_medium = form.best_medium or bests.get("MEDIUM")
            form.best_hard = form.best_hard or bests.get("HARD")
            slope = _deg_slope(grp)
            if slope is not None:
                form.deg_slope = slope
            drivers[int(driver_id)] = form

    if quali_id:
        q_laps = db.fetch_all_laps(quali_id)
        for driver_id, grp in q_laps.groupby("driver_id"):
            times = grp["lap_time_s"].dropna()
            if times.empty:
                continue
            if int(driver_id) in drivers:
                drivers[int(driver_id)].quali_time = float(times.min())
            else:
                row = grp.iloc[0]
                drivers[int(driver_id)] = DriverForm(
                    driver_id=int(driver_id),
                    code=str(row["code"]),
                    full_name=str(row["full_name"]),
                    team=str(row["team"]) if pd.notna(row.get("team")) else None,
                    quali_time=float(times.min()),
                )

    return sorted(drivers.values(), key=lambda d: d.quali_time or 999.0)


def weekend_session_types(year: int, round_no: int) -> list[str]:
    """Session types ingested for a round (empty list if none)."""
    sessions = db.fetch_weekend_sessions(year, round_no)
    if sessions.empty:
        return []
    return [str(t) for t in sessions["session_type"].tolist()]
