"""Linear tyre degradation model — pace loss per lap in stint."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from aris.models.blend import inverse_variance_blend

logger = logging.getLogger(__name__)

DEFAULT_COMPOUND_SLOPE: Final[dict[str, float]] = {
    "SOFT": 0.08,
    "MEDIUM": 0.05,
    "HARD": 0.03,
    "INTERMEDIATE": 0.04,
    "WET": 0.02,
}

OUT_LAP_PENALTY_S: Final[float] = 1.5
_MIN_SLOPE_VAR: Final[float] = 1e-6
_FALLBACK_SLOPE_VAR: Final[float] = 0.01

CIRCUIT_DEG_ENV = "ARIS_USE_CIRCUIT_DEG"
CIRCUIT_DEG_PATH = Path(__file__).resolve().parents[3] / "models" / "circuit_deg_slopes.json"
_DRY_COMPOUNDS = frozenset({"SOFT", "MEDIUM", "HARD"})
_CIRCUIT_DEG_ALIASES: Final[dict[str, str]] = {
    "zandvoort": "netherlands",
    "dutch": "netherlands",
    "monza": "italy",
    "spa": "belgium",
    "francorchamps": "belgium",
    "silverstone": "britain",
    "greatbritain": "britain",
    "imola": "imola",
    "emiliaromagna": "imola",
    "emilia_romagna": "imola",
    "interlagos": "brazil",
    "saopaulo": "brazil",
    "sao_paulo": "brazil",
    "jeddah": "saudi_arabia",
    "saudiarabia": "saudi_arabia",
    "melbourne": "australia",
    "suzuka": "japan",
    "shanghai": "china",
    "austin": "usa",
    "unitedstates": "usa",
    "cota": "usa",
    "vegas": "las_vegas",
    "lasvegas": "las_vegas",
    "yasmarina": "abu_dhabi",
    "abudhabi": "abu_dhabi",
    "sakhir": "bahrain",
    "baku": "azerbaijan",
    "montecarlo": "monaco",
    "montreal": "canada",
    "catalunya": "spain",
    "barcelona": "spain",
    "spielberg": "austria",
    "redbullring": "austria",
    "hungaroring": "hungary",
    "mexicocity": "mexico",
    "lusail": "qatar",
}


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
    """Seconds lost vs a fresh-tyre reference lap for this compound and stint age.

    When ``slopes`` is None, uses ``DEFAULT_COMPOUND_SLOPE``. Pass a track-specific
    override dict (from ``TrackConfig.compound_slopes``) to replace the globals for
    compounds present in that dict; missing compounds still fall back to MEDIUM /
    defaults via the same lookup rules as the global table.
    """
    if lap_in_stint < 1:
        raise ValueError(f"lap_in_stint must be >= 1, got {lap_in_stint}")
    if slopes:
        # Track override wins per compound; unspecified compounds use globals.
        table = {**DEFAULT_COMPOUND_SLOPE, **{normalize_compound(k): float(v) for k, v in slopes.items()}}
    else:
        table = DEFAULT_COMPOUND_SLOPE
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


def slope_mean_var(values: np.ndarray | list[float], *, min_obs: int = 2) -> tuple[float, float]:
    """Sample mean + variance of DegSlope observations (uninformative if too few)."""
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan")
    mean = float(np.mean(arr))
    if arr.size < min_obs:
        return mean, _FALLBACK_SLOPE_VAR
    if arr.size == 1:
        return mean, _FALLBACK_SLOPE_VAR
    return mean, max(float(np.var(arr, ddof=1)), _MIN_SLOPE_VAR)


def blend_slope_prior(
    prior_mean: float,
    prior_var: float,
    obs_mean: float,
    obs_var: float,
) -> float:
    """Precision-weighted (inverse-variance) blend of a historical prior with a session obs."""
    return inverse_variance_blend(prior_mean, obs_mean, prior_var, obs_var, min_var=_MIN_SLOPE_VAR)


def fit_track_compound_slopes(
    metrics: pd.DataFrame,
    *,
    session_col: str = "SessionKey",
    min_stints_prior: int = 3,
    min_stints_session: int = 2,
) -> dict[str, float]:
    """Fit track-specific compound slopes via session-level inverse-variance pooling.

    For each compound:
      1. Per session with enough DegSlope samples, estimate (mean, sample variance).
      2. Precision-weight blend those session estimates:
         ``sum(mean_s / var_s) / sum(1 / var_s)``.
         High-variance sessions (typical noisy FP2) contribute little; tight
         race stints dominate — same IV idea as tyre-prior / forecast blending.

    ``blend_slope_prior`` remains the two-source helper for a live weekend update
    (historical track prior vs new FP1/Sprint observation).

    Compounds without enough multi-session data keep ``DEFAULT_COMPOUND_SLOPE``.
    ``metrics`` must include Compound, DegSlope, and ``session_col``.
    """
    required = {"Compound", "DegSlope", session_col}
    missing = required - set(metrics.columns)
    if missing:
        raise ValueError(f"metrics missing columns: {sorted(missing)}")

    out: dict[str, float] = dict(DEFAULT_COMPOUND_SLOPE)
    work = metrics.dropna(subset=["DegSlope"]).copy()
    work["Compound"] = work["Compound"].map(normalize_compound)

    for compound, comp_grp in work.groupby("Compound"):
        sources: list[tuple[float, float]] = []
        for _sess, grp in comp_grp.groupby(session_col):
            if len(grp) < min_stints_session:
                continue
            mean, var = slope_mean_var(grp["DegSlope"].to_numpy())
            if np.isfinite(mean) and np.isfinite(var) and var > 0:
                sources.append((mean, max(var, _MIN_SLOPE_VAR)))

        if len(sources) >= 2:
            # Closed-form multi-source inverse-variance mean.
            num = sum(m / v for m, v in sources)
            den = sum(1.0 / v for _m, v in sources)
            out[str(compound)] = float(num / den)
        elif len(sources) == 1 and len(comp_grp) >= min_stints_prior:
            out[str(compound)] = float(sources[0][0])
        elif len(comp_grp) >= min_stints_prior:
            out[str(compound)] = float(comp_grp["DegSlope"].mean())
    return out


def circuit_deg_enabled(raw: str | bool | None = None) -> bool:
    """True only for explicit opt-in. ``0`` / ``false`` / unset are off."""
    if raw is True:
        return True
    if raw is False:
        return False
    if raw is None:
        raw = os.getenv(CIRCUIT_DEG_ENV, "")
    token = str(raw).strip().lower()
    return token in ("1", "true", "yes", "on")


def _normalize_circuit_key(circuit_key: str) -> str:
    token = (
        str(circuit_key)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )
    compact = token.replace("_", "")
    if token in _CIRCUIT_DEG_ALIASES:
        return _CIRCUIT_DEG_ALIASES[token]
    if compact in _CIRCUIT_DEG_ALIASES:
        return _CIRCUIT_DEG_ALIASES[compact]
    return token


@lru_cache(maxsize=4)
def _load_circuit_deg_file(path_str: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as extra:
        logger.warning("circuit deg JSON unreadable (%s): %s", path, extra)
        return {}
    return data if isinstance(data, dict) else {}


def clear_circuit_deg_cache() -> None:
    _load_circuit_deg_file.cache_clear()


def get_compound_slopes(circuit_key: str, year: int) -> dict[str, float]:
    """Per-circuit OLS slopes when ``ARIS_USE_CIRCUIT_DEG`` is on; else G1.5 defaults.

    Falls back to ``DEFAULT_COMPOUND_SLOPE`` when the flag is off, the file is
    missing, ``meta.max_year >= year`` (train-year leakage), the circuit is
    absent, or a compound pair has ``n_stints < 3``. Never applies INTERMEDIATE/WET.
    """
    prior = dict(DEFAULT_COMPOUND_SLOPE)
    if not circuit_deg_enabled():
        return prior
    data = _load_circuit_deg_file(str(CIRCUIT_DEG_PATH))
    if not data:
        return prior
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    max_year = meta.get("max_year")
    try:
        if max_year is not None and int(max_year) >= int(year):
            return prior
    except (TypeError, ValueError):
        return prior
    key = _normalize_circuit_key(circuit_key)
    circuit = data.get(key)
    if not isinstance(circuit, dict):
        return prior
    out = dict(prior)
    for compound, rec in circuit.items():
        name = normalize_compound(compound)
        if name not in _DRY_COMPOUNDS or not isinstance(rec, dict):
            continue
        try:
            n_stints = int(rec.get("n_stints", 0))
            slope = float(rec["slope"])
        except (TypeError, ValueError, KeyError):
            continue
        if n_stints < 3 or not np.isfinite(slope):
            continue
        out[name] = slope
    return out

