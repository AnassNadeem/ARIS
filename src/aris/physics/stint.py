"""Stint detection + per-stint metrics. Prototype lifted from notebook 04."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Stint:
    """One driver's continuous run on a single compound."""

    driver: str
    stint_id: int
    compound: str
    start_lap: int
    end_lap: int
    num_laps: int
    median_pace_s: float
    deg_slope_s_per_lap: float | None

    @property
    def length(self) -> int:
        return self.num_laps


def detect_stints(laps_df: pd.DataFrame) -> pd.DataFrame:
    """Enrich a laps frame with LapTimeS, CompoundChange, StintId (per-driver, 1-indexed).

    Stint boundaries: prefer FastF1's official ``Stint`` column when present.
    Otherwise split on compound change **or** pit-out, so same-compound
    consecutive tyre sets (HARD→HARD, MEDIUM→MEDIUM) are not merged. Merging
    those resets TyreLife mid-"stint" and corrupts DegSlope (Phase E3.1).
    """
    df = laps_df.sort_values(["Driver", "LapNumber"]).copy()
    df["LapTimeS"] = df["LapTime"].dt.total_seconds()
    df["CompoundChange"] = df.groupby("Driver")["Compound"].transform(lambda s: s != s.shift(1))

    use_ff1 = "Stint" in df.columns and df["Stint"].notna().any()
    stint_ids = pd.Series(index=df.index, dtype=int)
    for _drv, idx in df.groupby("Driver", sort=False).groups.items():
        g = df.loc[idx]
        if use_ff1 and g["Stint"].notna().any():
            filled = g["Stint"].astype("Float64").ffill().bfill()
            stint_ids.loc[idx] = pd.factorize(filled, sort=False)[0] + 1
        else:
            compound_change = g["Compound"] != g["Compound"].shift(1)
            if "PitOutTime" in g.columns:
                pit_out = g["PitOutTime"].notna()
            else:
                pit_out = pd.Series(False, index=g.index)
            stint_ids.loc[idx] = (compound_change | pit_out).cumsum().astype(int).to_numpy()
    df["StintId"] = stint_ids.astype(int)
    return df


def filter_clean_laps(enriched: pd.DataFrame) -> pd.DataFrame:
    """Drop laps that don't represent steady-state green-flag pace.

    Removes NaN-time laps, out-laps and in-laps, and any lap run under a
    non-green track status. The status filter keys on FastF1's `TrackStatus`
    string and keeps only `'1'` (all-clear); a lap whose status is a multi-code
    string like `'24'` (yellow + safety car during the lap) is dropped, since
    SC / VSC / yellow / red-flag laps inflate the baseline MAE (Week 2 flagged
    Miami and Australia for exactly this). When the frame carries no
    `TrackStatus` column the status filter is skipped, so synthetic frames and
    older callers are unaffected.
    """
    e = enriched.copy()
    e = e[e["LapTimeS"].notna()]
    e = e[e["PitOutTime"].isna() & e["PitInTime"].isna()]
    if "TrackStatus" in e.columns:
        e = e[e["TrackStatus"].astype("string").fillna("") == "1"]
    return e


def summarise_stints(enriched: pd.DataFrame) -> pd.DataFrame:
    """One row per (Driver, StintNumber) with start/end laps, num laps, median pace."""
    return (
        enriched.groupby(["Driver", "StintId"])
        .agg(
            Compound=("Compound", "first"),
            StartLap=("LapNumber", "min"),
            EndLap=("LapNumber", "max"),
            NumLaps=("LapNumber", "count"),
            MedianPaceS=("LapTimeS", "median"),
        )
        .reset_index()
        .rename(columns={"StintId": "StintNumber"})
    )


def compute_stint_metrics(enriched: pd.DataFrame, min_laps: int = 3) -> pd.DataFrame:
    """Per-stint summary including a TyreLife-vs-LapTimeS degradation slope.

    DegSlope is fit only on clean flying laps (``filter_clean_laps``: green
    flag, non-pit) excluding the first lap of each stint. Pre-E3.2 the fit pool
    kept SC/yellow laps, which inflated/deflated slopes on longer HARD runs.
    """
    e = enriched.copy()
    first_lap_of_stint = e.groupby(["Driver", "StintId"])["LapNumber"].transform("min")
    clean = filter_clean_laps(e)
    fit_pool = clean.loc[clean["LapNumber"] != first_lap_of_stint.loc[clean.index]]

    rows = []
    for (drv, sid), grp in e.groupby(["Driver", "StintId"]):
        fit = fit_pool[(fit_pool["Driver"] == drv) & (fit_pool["StintId"] == sid)]
        slope: float = np.nan
        if len(fit) >= min_laps and fit["TyreLife"].nunique() >= 2:
            try:
                x = fit["TyreLife"].to_numpy(dtype=float)
                y = fit["LapTimeS"].to_numpy(dtype=float)
                mask = np.isfinite(x) & np.isfinite(y)
                if int(mask.sum()) >= min_laps and np.unique(x[mask]).size >= 2:
                    slope, _ = np.polyfit(x[mask], y[mask], 1)
                    if not np.isfinite(slope):
                        slope = np.nan
            except np.linalg.LinAlgError:
                slope = np.nan
        rows.append(
            {
                "Driver": drv,
                "StintNumber": sid,
                "Compound": grp["Compound"].iloc[0],
                "StartLap": grp["LapNumber"].min(),
                "EndLap": grp["LapNumber"].max(),
                "NumLaps": len(grp),
                "MedianPaceS": grp["LapTimeS"].median(),
                "DegSlope": slope,
            }
        )
    return pd.DataFrame(rows)


def stints_from_metrics(metrics: pd.DataFrame) -> list[Stint]:
    """Materialise the metrics frame into a list of frozen Stint records."""
    out: list[Stint] = []
    for row in metrics.itertuples(index=False):
        slope = row.DegSlope
        out.append(
            Stint(
                driver=str(row.Driver),
                stint_id=int(row.StintNumber),
                compound=str(row.Compound),
                start_lap=int(row.StartLap),
                end_lap=int(row.EndLap),
                num_laps=int(row.NumLaps),
                median_pace_s=float(row.MedianPaceS),
                deg_slope_s_per_lap=None if pd.isna(slope) else float(slope),
            )
        )
    return out
