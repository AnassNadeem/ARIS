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
    """Enrich a laps frame with LapTimeS, CompoundChange, StintId (per-driver, 1-indexed)."""
    df = laps_df.sort_values(["Driver", "LapNumber"]).copy()
    df["LapTimeS"] = df["LapTime"].dt.total_seconds()
    df["CompoundChange"] = df.groupby("Driver")["Compound"].transform(lambda s: s != s.shift(1))
    df["StintId"] = df.groupby("Driver")["CompoundChange"].cumsum()
    return df


def filter_clean_laps(enriched: pd.DataFrame) -> pd.DataFrame:
    """Drop laps that don't represent steady-state pace: out-laps, in-laps, NaN times."""
    e = enriched.copy()
    e = e[e["LapTimeS"].notna()]
    e = e[e["PitOutTime"].isna() & e["PitInTime"].isna()]
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
    """Per-stint summary including a TyreLife-vs-LapTimeS degradation slope."""
    e = enriched.copy()
    first_lap_of_stint = e.groupby(["Driver", "StintId"])["LapNumber"].transform("min")
    fit_pool = e[
        (e["LapNumber"] != first_lap_of_stint)
        & e["PitInTime"].isna()
        & e["LapTimeS"].notna()
    ]

    rows = []
    for (drv, sid), grp in e.groupby(["Driver", "StintId"]):
        fit = fit_pool[(fit_pool["Driver"] == drv) & (fit_pool["StintId"] == sid)]
        slope: float = np.nan
        if len(fit) >= min_laps and fit["TyreLife"].nunique() >= 2:
            slope, _ = np.polyfit(fit["TyreLife"], fit["LapTimeS"], 1)
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
