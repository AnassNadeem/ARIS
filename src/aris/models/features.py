"""Leakage-safe feature frame for lap-time residual modelling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aris.physics.bicycle import Car, StintState, Track, bahrain_2024
from aris.physics.bicycle import predict_lap_time as physics_predict
from aris.physics.stint import detect_stints, filter_clean_laps
from aris.tracks import load_track_config

_FUEL_START_KG = 110.0
_FUEL_BURN_PER_LAP = 1.7

_COMPOUND_CODE = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}

FEATURE_COLS = [
    "compound_code",
    "tyre_life",
    "fuel_kg",
    "lag1_pace",
    "lag2_pace",
    "stint_roll3",
    "physics_pred",
]


def _compound_code(compound: str | None) -> int:
    return _COMPOUND_CODE.get(str(compound or "MEDIUM").upper(), 1)


def estimate_fuel_kg(lap_number: int, total_laps: int = 57) -> float:
    burned = _FUEL_BURN_PER_LAP * max(0, lap_number - 1)
    return max(0.0, _FUEL_START_KG - burned)


def resolve_track(gp_or_country: str) -> Track:
    """Load bicycle Track for a GP/country name (YAML corners when present)."""
    return load_track_config(gp_or_country).load_physics()


def physics_prediction_row(row: pd.Series, track: Track | None = None) -> float:
    t = track or bahrain_2024()
    state = StintState(
        car=Car(),
        track=t,
        fuel_kg=float(row.get("fuel_kg", 0.0)),
        pit_lap=bool(row.get("pit_lap", False)),
        compound=str(row.get("compound", "MEDIUM")),
        lap_in_stint=int(row.get("tyre_life", 1) or 1),
    )
    return physics_predict(state)


def build_feature_frame(
    laps_df: pd.DataFrame,
    *,
    race_id: str,
    track: Track | None = None,
    total_laps: int | None = None,
) -> pd.DataFrame:
    enriched = detect_stints(laps_df)
    clean = filter_clean_laps(enriched)
    if clean.empty:
        return pd.DataFrame()

    t = track or bahrain_2024()
    laps_total = total_laps if total_laps is not None else 57

    df = clean.copy()
    df["race_id"] = race_id
    df["compound_code"] = df["Compound"].map(_compound_code)
    df["tyre_life"] = df["TyreLife"].fillna(1).astype(int)
    df["fuel_kg"] = df["LapNumber"].map(lambda n: estimate_fuel_kg(int(n), total_laps=laps_total))
    df["pit_lap"] = False
    df["compound"] = df["Compound"].fillna("MEDIUM")

    grouped = df.groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
    df["lag1_pace"] = grouped.shift(1)
    df["lag2_pace"] = grouped.shift(2)
    df["stint_roll3"] = grouped.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    df["physics_pred"] = df.apply(lambda row: physics_prediction_row(row, track=t), axis=1)
    df["target"] = df["LapTimeS"]
    df["residual"] = df["target"] - df["physics_pred"]

    out = df[
        ["race_id", "Driver", "LapNumber", "StintId", "target", "residual", *FEATURE_COLS]
    ].copy()
    return out.dropna(subset=["lag1_pace", "target"])


def feature_matrix(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = frame[FEATURE_COLS].to_numpy(dtype=float)
    y_res = frame["residual"].to_numpy(dtype=float)
    y_true = frame["target"].to_numpy(dtype=float)
    return x, y_res, y_true


def build_from_fastf1(year: int, gp: str) -> pd.DataFrame:
    import fastf1

    from aris.tracks import _match_track_file

    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    event_name = str(session.event.EventName)
    location = str(session.event.Location)
    country = str(session.event.Country)
    race_id = f"{year}-{event_name.replace(' ', '_')}"

    # Resolve track YAML: GP arg → event name → location → country.
    # Location before country so shared-country circuits (Italy/USA/Germany)
    # and 2026 Madrid vs Barcelona resolve correctly.
    if _match_track_file(gp) is not None:
        cfg = load_track_config(gp, year=year)
    elif _match_track_file(event_name) is not None:
        cfg = load_track_config(event_name, year=year)
    elif _match_track_file(location) is not None:
        cfg = load_track_config(location, year=year)
    else:
        cfg = load_track_config(country, year=year)

    track = cfg.load_physics()
    total = int(session.total_laps) if session.total_laps else cfg.total_laps
    return build_feature_frame(
        session.laps, race_id=race_id, track=track, total_laps=total
    )
