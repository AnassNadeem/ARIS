"""Build race_state dict from FastF1 lap data for ARIS chat and live screen."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from aris.eval.scoring import mae
from aris.models.predict import predict_lap_time, predict_physics
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE
from aris.tracks import load_track_config

from dashboard.utils.fastf1_loader import get_driver_laps
from dashboard.utils.monte_carlo import TYRE_LIFE_ESTIMATE as _TYRE_LIFE


def _pace_lags(driver_laps: pd.DataFrame, lap_number: int) -> tuple[float | None, float | None, float | None]:
    prior = driver_laps[driver_laps["lap_number"] < lap_number].sort_values("lap_number")
    times = prior["lap_time_s"].dropna().tolist()
    if not times:
        return None, None, None
    lag1 = times[-1]
    lag2 = times[-2] if len(times) >= 2 else lag1
    roll3 = sum(times[-3:]) / min(3, len(times[-3:]))
    return float(lag1), float(lag2), float(roll3)


def compute_standings_at_lap(laps_df: pd.DataFrame, lap_number: int) -> list[dict]:
    """Cumulative time standings at end of lap."""
    rows = []
    for driver, grp in laps_df.groupby("driver"):
        grp = grp.sort_values("lap_number")
        cum = grp[grp["lap_number"] <= lap_number]["lap_time_s"].dropna().sum()
        current = grp[grp["lap_number"] == lap_number]
        if current.empty:
            continue
        r = current.iloc[0]
        rows.append({
            "driver": driver,
            "cumulative_s": float(cum),
            "last_lap_s": float(r["lap_time_s"]) if pd.notna(r.get("lap_time_s")) else None,
            "compound": str(r.get("compound", "MEDIUM")),
            "tyre_life": int(r.get("tyre_life", 1)),
            "sector_1_s": r.get("sector_1_s"),
            "sector_2_s": r.get("sector_2_s"),
            "sector_3_s": r.get("sector_3_s"),
        })
    rows.sort(key=lambda x: x["cumulative_s"])
    leader = rows[0]["cumulative_s"] if rows else 0.0
    for i, row in enumerate(rows):
        row["pos"] = i + 1
        row["gap_s"] = row["cumulative_s"] - leader
        row["gap_ahead_s"] = (
            row["cumulative_s"] - rows[i - 1]["cumulative_s"] if i > 0 else None
        )
        row["gap_behind_s"] = (
            rows[i + 1]["cumulative_s"] - row["cumulative_s"] if i < len(rows) - 1 else None
        )
    return rows


def predict_for_lap(
    driver_laps: pd.DataFrame,
    lap_number: int,
    *,
    total_laps: int = 57,
) -> dict[str, float | None]:
    """ARIS prediction = physics + ML residual."""
    row_df = driver_laps[driver_laps["lap_number"] == lap_number]
    if row_df.empty:
        return {"physics": None, "ml_residual": None, "aris_pred": None, "actual": None, "error": None}

    row = row_df.iloc[0]
    compound = str(row.get("compound", "MEDIUM"))
    tyre_life = int(row.get("tyre_life", 1))
    from aris.models.features import estimate_fuel_kg

    fuel = estimate_fuel_kg(lap_number, total_laps=total_laps)
    lag1, lag2, roll3 = _pace_lags(driver_laps, lap_number)

    physics = predict_physics(compound=compound, tyre_life=tyre_life, fuel_kg=fuel)
    aris_pred = predict_lap_time(
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel,
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
    )
    ml_residual = aris_pred - physics if lag1 is not None else 0.0
    actual = float(row["lap_time_s"]) if pd.notna(row.get("lap_time_s")) else None
    error = (aris_pred - actual) if actual is not None else None

    return {
        "physics": physics,
        "ml_residual": ml_residual,
        "aris_pred": aris_pred,
        "actual": actual,
        "error": error,
    }


def compute_race_mae(driver_laps: pd.DataFrame, through_lap: int, total_laps: int = 57) -> float | None:
    actuals = []
    preds = []
    for lap in range(2, through_lap + 1):
        p = predict_for_lap(driver_laps, lap, total_laps=total_laps)
        if p["actual"] is not None and p["aris_pred"] is not None:
            actuals.append(p["actual"])
            preds.append(p["aris_pred"])
    if not actuals:
        return None
    return float(mae(np.array(actuals), np.array(preds)))


def get_stint_info(strategy: dict | None, current_lap: int) -> dict:
    """Current stint compound and number from selected strategy."""
    if not strategy:
        return {"compound": "MEDIUM", "stint_num": 1, "laps_on_tyre": current_lap}

    compounds = strategy.get("compounds", ["SOFT", "MEDIUM", "HARD"])
    pit_laps = strategy.get("pit_laps", [18, 40])
    stint = 1
    compound = compounds[0]
    stint_start = 1
    for i, pit_lap in enumerate(pit_laps):
        if current_lap > pit_lap:
            stint = i + 2
            compound = compounds[min(stint - 1, len(compounds) - 1)]
            stint_start = pit_lap + 1
        else:
            break
    laps_on = current_lap - stint_start + 1
    return {"compound": compound, "stint_num": stint, "laps_on_tyre": laps_on, "stint_start": stint_start}


def build_race_state(
    *,
    laps_df: pd.DataFrame,
    driver_code: str,
    current_lap: int,
    total_laps: int,
    country: str,
    strategy: dict | None = None,
    mc_probs: dict | None = None,
    weather: dict | None = None,
) -> dict[str, Any]:
    """Full race_state dict for ARIS chat."""
    driver_laps = get_driver_laps(laps_df, driver_code)
    standings = compute_standings_at_lap(laps_df, current_lap)
    my_row = next((r for r in standings if r["driver"] == driver_code), None)
    preds = predict_for_lap(driver_laps, current_lap, total_laps=total_laps)
    stint = get_stint_info(strategy, current_lap)
    track_cfg = load_track_config(country)
    deg_slope = DEFAULT_COMPOUND_SLOPE.get(stint["compound"], 0.05)
    tyre_life_max = _TYRE_LIFE.get(stint["compound"], 34)

    pit_laps = strategy.get("pit_laps", [40, 44]) if strategy else [40, 44]
    pit_window = {"open": pit_laps[0] if pit_laps else 40, "close": (pit_laps[-1] + 4) if pit_laps else 44, "optimal": pit_laps[0] if pit_laps else 41}

    cars = [
        {
            "pos": r["pos"],
            "driver": r["driver"],
            "tyre": r["compound"],
            "age": r["tyre_life"],
            "last_lap": r["last_lap_s"],
            "gap": r["gap_s"],
        }
        for r in standings
    ]

    from aris.models.features import estimate_fuel_kg

    fuel_remaining = estimate_fuel_kg(current_lap, total_laps=total_laps)

    return {
        "current_lap": current_lap,
        "total_laps": total_laps,
        "country": country,
        "driver": driver_code,
        "position": my_row["pos"] if my_row else None,
        "gap_to_leader_s": my_row["gap_s"] if my_row else 0.0,
        "gap_behind_s": my_row.get("gap_behind_s") if my_row else None,
        "gap_ahead_s": my_row.get("gap_ahead_s") if my_row else None,
        "compound": stint["compound"],
        "tyre_life": stint["laps_on_tyre"],
        "stint_num": stint["stint_num"],
        "deg_rate": deg_slope,
        "tyre_life_max": tyre_life_max,
        "fuel_kg": fuel_remaining,
        "track_temp_c": (weather or {}).get("track_temp_c", 38),
        "aris_pred": preds.get("aris_pred"),
        "actual": preds.get("actual"),
        "ml_residual": preds.get("ml_residual"),
        "race_mae": compute_race_mae(driver_laps, current_lap, total_laps),
        "my_strategy": strategy,
        "pit_window": pit_window,
        "mc_probabilities": mc_probs or {"p1": 0.68, "p2": 0.24, "p3_plus": 0.08},
        "cars": cars,
        "standings": standings,
    }
