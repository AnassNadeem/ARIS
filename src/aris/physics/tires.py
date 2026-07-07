"""Linear tyre degradation model — pace loss per lap in stint."""

from __future__ import annotations

from typing import Final

import pandas as pd

DEFAULT_COMPOUND_SLOPE: Final[dict[str, float]] = {
    "SOFT": 0.08,
    "MEDIUM": 0.05,
    "HARD": 0.03,
    "INTERMEDIATE": 0.04,
    "WET": 0.02,
}

OUT_LAP_PENALTY_S: Final[float] = 1.5


def normalize_compound(compound: str | None) -> str:
    if not compound:
        return "MEDIUM"
    return str(compound).strip().upper()


def tire_pace_loss(
    compound: str,
    lap_in_stint: int,
    *,
    slopes: dict[str, float] | None = None,
) -> float:
    """Seconds lost vs a fresh-tyre reference lap for this compound and stint age."""
    if lap_in_stint < 1:
        raise ValueError(f"lap_in_stint must be >= 1, got {lap_in_stint}")
    table = slopes or DEFAULT_COMPOUND_SLOPE
    key = normalize_compound(compound)
    slope = table.get(key, table.get("MEDIUM", 0.05))
    deg = slope * max(0, lap_in_stint - 1)
    out_lap = OUT_LAP_PENALTY_S if lap_in_stint == 1 else 0.0
    return deg + out_lap


def fit_compound_slopes(metrics: pd.DataFrame, min_stints: int = 3) -> dict[str, float]:
    """Median DegSlope per compound from a compute_stint_metrics frame."""
    if "Compound" not in metrics.columns or "DegSlope" not in metrics.columns:
        raise ValueError("metrics must carry Compound and DegSlope columns")
    slopes: dict[str, float] = dict(DEFAULT_COMPOUND_SLOPE)
    for compound, grp in metrics.groupby("Compound"):
        valid = grp["DegSlope"].dropna()
        if len(valid) >= min_stints:
            slopes[normalize_compound(str(compound))] = float(valid.median())
    return slopes
