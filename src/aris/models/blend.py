"""Precision-weighted (inverse-variance) forecast combination.

Blends two point predictors for the same lap using rolling error variances
estimated from recent causal history — the same inverse-variance idea intended
for tyre-prior blending, applied here to physics+residual vs MA(2).
"""

from __future__ import annotations

import numpy as np


def inverse_variance_blend(
    pred_a: float,
    pred_b: float,
    var_a: float,
    var_b: float,
    *,
    min_var: float = 1e-6,
) -> float:
    """Precision-weighted mean of two predictions.

    weight_i = 1 / var_i  (floored at min_var). If either variance is
    non-finite, fall back to the other prediction; if both are unusable,
    return the mean of the two predictions.
    """
    va = float(var_a) if np.isfinite(var_a) else float("nan")
    vb = float(var_b) if np.isfinite(var_b) else float("nan")
    if not np.isfinite(va) and not np.isfinite(vb):
        return 0.5 * (float(pred_a) + float(pred_b))
    if not np.isfinite(va):
        return float(pred_b)
    if not np.isfinite(vb):
        return float(pred_a)
    va = max(va, min_var)
    vb = max(vb, min_var)
    wa = 1.0 / va
    wb = 1.0 / vb
    return float((wa * pred_a + wb * pred_b) / (wa + wb))


def rolling_error_variance(
    errors: list[float] | np.ndarray,
    *,
    min_obs: int = 3,
    fallback: float = 1.0,
) -> float:
    """Mean squared error of recent signed errors (bias-aware precision).

    Historically named ``rolling_error_variance``, but sample variance of
    signed errors ignores a constant bias — a predictor that is always 1.5 s
    slow with tiny scatter then receives too much IV blend weight (Phase E3.4:
    Australia/Italy/Belgium/…). MSE = bias² + variance is the right risk
    measure for inverse-variance combination against the truth.

    Empty / too-short history → ``fallback`` (uninformative prior).
    """
    arr = np.asarray(list(errors), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < min_obs:
        return float(fallback)
    return float(np.mean(np.square(arr)))
