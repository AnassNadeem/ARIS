"""Pure-NumPy scoring primitives. Fails loud on shape / NaN issues."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def _validated_pair(y_true: ArrayLike, y_pred: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    if yt.shape != yp.shape:
        raise ValueError(f"shape mismatch: y_true {yt.shape} vs y_pred {yp.shape}")
    if yt.size == 0:
        raise ValueError("empty arrays — nothing to score")
    if np.isnan(yt).any() or np.isnan(yp).any():
        raise ValueError("NaN present in y_true or y_pred — drop NaNs before scoring")
    return yt, yp


def mae(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Mean absolute error in the same units as the inputs."""
    yt, yp = _validated_pair(y_true, y_pred)
    return float(np.mean(np.abs(yt - yp)))


def rmse(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Root-mean-squared error in the same units as the inputs."""
    yt, yp = _validated_pair(y_true, y_pred)
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def per_race_mae(
    y_true: ArrayLike,
    y_pred: ArrayLike,
    race_ids: ArrayLike,
) -> dict[str, float]:
    """MAE per unique race_id. Keys are race_ids (stringified); values are floats."""
    yt, yp = _validated_pair(y_true, y_pred)
    rids = np.asarray(race_ids)
    if rids.shape != yt.shape:
        raise ValueError(f"race_ids shape {rids.shape} != y_true shape {yt.shape}")
    out: dict[str, float] = {}
    for rid in np.unique(rids):
        mask = rids == rid
        out[str(rid)] = float(np.mean(np.abs(yt[mask] - yp[mask])))
    return out
