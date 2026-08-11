"""Unified lap-time predictor: physics + tyres + optional XGBoost residual."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import numpy as np
import pandas as pd

from aris.models.blend import inverse_variance_blend, rolling_error_variance
from aris.models.features import FEATURE_COLS, _compound_code, physics_prediction_row
from aris.models.residual import DEFAULT_MODEL_PATH, ResidualModel
from aris.physics.bicycle import Car, StintState, Track, bahrain_2024
from aris.physics.bicycle import predict_lap_time as physics_predict

_MODEL: ResidualModel | None = None
_BLEND_WINDOW = 8
_BLEND_MIN_OBS = 3
_BLEND_FALLBACK_VAR = 1.0


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
    # Prefer the feature-frame physics_pred when present so eval/training stay
    # consistent with whatever Track build_from_fastf1 resolved for that race.
    if track is None and "physics_pred" in row.index and pd.notna(row["physics_pred"]):
        physics = float(row["physics_pred"])
    else:
        physics = physics_prediction_row(row, track=track)
    model = _get_model()
    if model is None:
        return physics
    feat_row = row[FEATURE_COLS] if all(c in row.index for c in FEATURE_COLS) else row
    residual = float(model.predict_residual(pd.DataFrame([feat_row]))[0])
    return physics + residual


def ma2_from_lags(lag1_pace: float | None, lag2_pace: float | None) -> float | None:
    """MA(2) point prediction from causal lag features (same as baseline window=2)."""
    if lag1_pace is None or lag2_pace is None:
        return None
    if not (np.isfinite(lag1_pace) and np.isfinite(lag2_pace)):
        return None
    return 0.5 * (float(lag1_pace) + float(lag2_pace))


def blend_physics_residual_with_ma2(
    pred_residual: float,
    pred_ma2: float,
    recent_residual_errors: Sequence[float],
    recent_ma2_errors: Sequence[float],
) -> float:
    """Thin wrapper: inverse-variance blend of physics+residual vs MA(2)."""
    var_r = rolling_error_variance(
        list(recent_residual_errors)[-_BLEND_WINDOW:],
        min_obs=_BLEND_MIN_OBS,
        fallback=_BLEND_FALLBACK_VAR,
    )
    var_m = rolling_error_variance(
        list(recent_ma2_errors)[-_BLEND_WINDOW:],
        min_obs=_BLEND_MIN_OBS,
        fallback=_BLEND_FALLBACK_VAR,
    )
    return inverse_variance_blend(pred_residual, pred_ma2, var_r, var_m)


def predict_blended_frame(frame: pd.DataFrame, track: Track | None = None) -> np.ndarray:
    """Score a feature frame with causal per-driver rolling-error blend.

    Laps lacking lag2 (MA(2) undefined) fall back to physics+residual alone.
    Variances update only from past errors for that driver within the frame.
    """
    if frame.empty:
        return np.array([], dtype=float)

    work = frame.sort_values(["Driver", "LapNumber"])
    preds_by_idx: dict[object, float] = {}
    err_r: dict[str, list[float]] = defaultdict(list)
    err_m: dict[str, list[float]] = defaultdict(list)

    for idx, row in work.iterrows():
        driver = str(row["Driver"])
        y_true = float(row["target"])
        pred_r = predict_from_lap_row(row, track=track)
        lag1 = float(row["lag1_pace"]) if pd.notna(row.get("lag1_pace")) else None
        lag2 = float(row["lag2_pace"]) if pd.notna(row.get("lag2_pace")) else None
        pred_m = ma2_from_lags(lag1, lag2)

        if pred_m is None:
            preds_by_idx[idx] = pred_r
            err_r[driver].append(y_true - pred_r)
            continue

        y_hat = blend_physics_residual_with_ma2(
            pred_r, pred_m, err_r[driver], err_m[driver]
        )
        preds_by_idx[idx] = y_hat
        err_r[driver].append(y_true - pred_r)
        err_m[driver].append(y_true - pred_m)

    return np.array([preds_by_idx[idx] for idx in frame.index], dtype=float)
