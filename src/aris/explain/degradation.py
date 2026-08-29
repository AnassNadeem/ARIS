"""Tire degradation curves: bicycle predicted vs FastF1 actual (fuel-adjusted)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from aris.explain.session import (
    DEFAULT_SESSION_ID,
    ExplainBundle,
    detect_stints_inplace,
    driver_laps,
    load_explain_bundle,
)
from aris.models.features import estimate_fuel_kg
from aris.physics.tires import (
    OUT_LAP_PENALTY_S,
    get_deg_slope,
    normalize_compound,
)
from aris.physics.tyre_warmup import tyre_warmup_for_lap
from aris.simulate import fuel_correction_s


def get_degradation_curve(
    driver: str,
    stint_id: int | None = None,
    start_lap: int | None = None,
    end_lap: int | None = None,
    *,
    session_id: str | None = None,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    bundle: ExplainBundle | None = None,
) -> dict[str, Any]:
    """Predicted vs actual deg (seconds) for one stint.

    ``predicted_deg_s`` is bicycle internals: slope × (age−1) + warmup + out-lap.
    ``actual_deg_s`` is fuel-adjusted FastF1 lap time minus the stint's fresh baseline.
    """
    data = bundle or load_explain_bundle(
        session_id or DEFAULT_SESSION_ID,
        year=year,
        round_number=round_number,
        session_type=session_type,
    )
    code = str(driver).upper()
    laps = detect_stints_inplace(driver_laps(data, code))
    if laps.empty:
        return _empty_curve(data, code, stint_id)

    stints = _stint_index(laps)
    chosen = _pick_stint(stints, stint_id, start_lap, end_lap, laps)
    if chosen is None:
        return _empty_curve(data, code, stint_id)

    sid, compound, s0, s1 = chosen
    window = laps[(laps["LapNumber"] >= s0) & (laps["LapNumber"] <= s1)].copy()
    window = window.sort_values("LapNumber")
    if start_lap is not None:
        window = window[window["LapNumber"] >= int(start_lap)]
    if end_lap is not None:
        window = window[window["LapNumber"] <= int(end_lap)]

    fuel_start = estimate_fuel_kg(int(s0), total_laps=data.total_laps)
    ages: list[int] = []
    pred: list[float] = []
    actual: list[float | None] = []
    lap_numbers: list[int] = []
    fuel_adj_vals: list[float] = []

    for rec in window.itertuples(index=False):
        lap_no = int(getattr(rec, "LapNumber"))
        age = _tyre_age(rec, laps=window, start_lap=s0)
        lap_s = _lap_time_s(rec)
        if lap_s is None:
            continue
        fuel = estimate_fuel_kg(lap_no, total_laps=data.total_laps)
        fuel_adj = float(lap_s) - fuel_correction_s(fuel)
        fuel_adj_vals.append(fuel_adj)
        ages.append(age)
        lap_numbers.append(lap_no)
        pred.append(
            _predicted_deg_s(
                compound,
                age,
                circuit=data.circuit,
                year=data.year,
                round_number=data.round_number,
                fuel_kg=fuel,
                fuel_start_kg=fuel_start,
            )
        )
        actual.append(None)  # filled after baseline

    baseline = _fresh_baseline(fuel_adj_vals, ages)
    actual = [round(v - baseline, 4) if v is not None else None for v in fuel_adj_vals]

    return {
        "tyre_age": ages,
        "predicted_deg_s": [round(v, 4) for v in pred],
        "actual_deg_s": actual,
        "lap_number": lap_numbers,
        "compound": compound,
        "circuit": data.circuit,
        "session_type": data.session_type,
        "session_id": data.session_id,
        "driver": code,
        "stint_id": sid,
        "start_lap": int(s0),
        "end_lap": int(s1),
        "fresh_baseline_s": round(float(baseline), 4),
        "available_stints": [
            {
                "stint_id": s["stint_id"],
                "compound": s["compound"],
                "start_lap": s["start_lap"],
                "end_lap": s["end_lap"],
            }
            for s in stints
        ],
    }


def _predicted_deg_s(
    compound: str,
    age: int,
    *,
    circuit: str,
    year: int,
    round_number: int,
    fuel_kg: float,
    fuel_start_kg: float,
) -> float:
    """Bicycle deg vs a fuel-corrected fresh flying lap: slope×(age−1) + warmup + out-lap + fuel delta."""
    slope = get_deg_slope(
        compound,
        circuit_id=circuit,
        year=year,
        round_number=round_number,
    )
    deg = float(slope) * max(0, int(age) - 1)
    warmup = tyre_warmup_for_lap(compound, int(age))
    out_lap = OUT_LAP_PENALTY_S if int(age) <= 1 else 0.0
    fuel_delta = fuel_correction_s(fuel_kg) - fuel_correction_s(fuel_start_kg)
    return deg + warmup + out_lap + fuel_delta


def _fresh_baseline(fuel_adj: list[float], ages: list[int]) -> float:
    """Fuel-adjusted reference: median of first flying laps (age 2–4), else first sample."""
    flying = [v for v, a in zip(fuel_adj, ages) if 2 <= a <= 4]
    if flying:
        return float(np.median(flying))
    if fuel_adj:
        return float(fuel_adj[0])
    return 0.0


def _stint_index(laps: pd.DataFrame) -> list[dict[str, Any]]:
    col = "StintId" if "StintId" in laps.columns else "Stint"
    if col not in laps.columns:
        if laps.empty:
            return []
        start = int(laps["LapNumber"].min())
        end = int(laps["LapNumber"].max())
        compound = normalize_compound(_first_str(laps, "Compound"))
        return [{"stint_id": 1, "compound": compound, "start_lap": start, "end_lap": end}]
    out: list[dict[str, Any]] = []
    for sid, grp in laps.groupby(col, sort=True):
        try:
            n = int(sid)
        except (TypeError, ValueError):
            continue
        compound = normalize_compound(_first_str(grp, "Compound"))
        out.append(
            {
                "stint_id": n,
                "compound": compound,
                "start_lap": int(grp["LapNumber"].min()),
                "end_lap": int(grp["LapNumber"].max()),
            }
        )
    return out


def _pick_stint(
    stints: list[dict[str, Any]],
    stint_id: int | None,
    start_lap: int | None,
    end_lap: int | None,
    laps: pd.DataFrame,
) -> tuple[int, str, int, int] | None:
    if not stints:
        return None
    if stint_id is not None:
        for s in stints:
            if s["stint_id"] == int(stint_id):
                return s["stint_id"], s["compound"], s["start_lap"], s["end_lap"]
    if start_lap is not None or end_lap is not None:
        lo = int(start_lap or laps["LapNumber"].min())
        hi = int(end_lap or laps["LapNumber"].max())
        overlap = [
            s
            for s in stints
            if not (s["end_lap"] < lo or s["start_lap"] > hi)
        ]
        if overlap:
            s = max(overlap, key=lambda x: min(x["end_lap"], hi) - max(x["start_lap"], lo))
            return s["stint_id"], s["compound"], max(s["start_lap"], lo), min(s["end_lap"], hi)
    s = stints[-1]
    return s["stint_id"], s["compound"], s["start_lap"], s["end_lap"]


def _tyre_age(rec: Any, *, laps: pd.DataFrame, start_lap: int) -> int:
    life = getattr(rec, "TyreLife", None)
    try:
        if life is not None and not (isinstance(life, float) and np.isnan(life)):
            n = int(life)
            if n >= 1:
                return n
    except (TypeError, ValueError):
        pass
    lap_no = int(getattr(rec, "LapNumber"))
    return max(1, lap_no - int(start_lap) + 1)


def _lap_time_s(rec: Any) -> float | None:
    raw = getattr(rec, "LapTimeS", None)
    if raw is not None and not (isinstance(raw, float) and np.isnan(raw)):
        try:
            v = float(raw)
            return v if np.isfinite(v) else None
        except (TypeError, ValueError):
            pass
    lt = getattr(rec, "LapTime", None)
    if lt is not None and hasattr(lt, "total_seconds"):
        try:
            v = float(lt.total_seconds())
            return v if np.isfinite(v) else None
        except (TypeError, ValueError):
            return None
    return None


def _first_str(frame: pd.DataFrame, col: str) -> str:
    if col not in frame.columns or frame.empty:
        return "MEDIUM"
    val = frame[col].dropna()
    if val.empty:
        return "MEDIUM"
    return str(val.iloc[0])


def _empty_curve(data: ExplainBundle, driver: str, stint_id: int | None) -> dict[str, Any]:
    return {
        "tyre_age": [],
        "predicted_deg_s": [],
        "actual_deg_s": [],
        "lap_number": [],
        "compound": "MEDIUM",
        "circuit": data.circuit,
        "session_type": data.session_type,
        "session_id": data.session_id,
        "driver": driver,
        "stint_id": stint_id,
        "start_lap": None,
        "end_lap": None,
        "fresh_baseline_s": None,
        "available_stints": [],
    }
