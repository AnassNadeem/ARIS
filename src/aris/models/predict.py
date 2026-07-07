"""Unified lap-time predictor: physics + tyres + optional XGBoost residual."""

from __future__ import annotations

import pandas as pd

from aris.models.features import FEATURE_COLS, _compound_code, physics_prediction_row
from aris.models.residual import DEFAULT_MODEL_PATH, ResidualModel
from aris.physics.bicycle import Car, StintState, Track, bahrain_2024
from aris.physics.bicycle import predict_lap_time as physics_predict

_MODEL: ResidualModel | None = None


def _get_model() -> ResidualModel | None:
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    if DEFAULT_MODEL_PATH.exists():
        _MODEL = ResidualModel.load()
        return _MODEL
    return None


def reset_model_cache() -> None:
    global _MODEL
    _MODEL = None


def predict_physics(
    *,
    compound: str = "MEDIUM",
    tyre_life: int = 1,
    fuel_kg: float = 0.0,
    pit_lap: bool = False,
    track: Track | None = None,
) -> float:
    t = track or bahrain_2024()
    state = StintState(
        car=Car(),
        track=t,
        fuel_kg=fuel_kg,
        pit_lap=pit_lap,
        compound=compound,
        lap_in_stint=tyre_life,
    )
    return physics_predict(state)


def predict_lap_time(
    *,
    compound: str = "MEDIUM",
    tyre_life: int = 1,
    fuel_kg: float = 0.0,
    pit_lap: bool = False,
    track: Track | None = None,
    lag1_pace: float | None = None,
    lag2_pace: float | None = None,
    stint_roll3: float | None = None,
    compound_code: int | None = None,
) -> float:
    physics = predict_physics(
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel_kg,
        pit_lap=pit_lap,
        track=track,
    )
    model = _get_model()
    if model is None or lag1_pace is None:
        return physics

    code = compound_code if compound_code is not None else _compound_code(compound)
    row = pd.Series(
        {
            "compound_code": code,
            "tyre_life": tyre_life,
            "fuel_kg": fuel_kg,
            "lag1_pace": lag1_pace,
            "lag2_pace": lag2_pace if lag2_pace is not None else lag1_pace,
            "stint_roll3": stint_roll3 if stint_roll3 is not None else lag1_pace,
            "physics_pred": physics,
        }
    )
    residual = float(model.predict_residual(pd.DataFrame([row]))[0])
    return physics + residual


def predict_from_lap_row(row: pd.Series, track: Track | None = None) -> float:
    physics = physics_prediction_row(row, track=track)
    model = _get_model()
    if model is None:
        return physics
    feat_row = row[FEATURE_COLS] if all(c in row.index for c in FEATURE_COLS) else row
    residual = float(model.predict_residual(pd.DataFrame([feat_row]))[0])
    return physics + residual
