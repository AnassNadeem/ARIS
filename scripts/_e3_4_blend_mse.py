"""E3.4 — check whether blend uses variance (ignores bias) vs MSE."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.models.blend import inverse_variance_blend, rolling_error_variance  # noqa: E402
from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import (  # noqa: E402
    _BLEND_MIN_OBS,
    _BLEND_WINDOW,
    ma2_from_lags,
    predict_from_lap_row,
    reset_model_cache,
)

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))


def analyse(gp: str) -> None:
    reset_model_cache()
    frame = build_from_fastf1(2024, gp)
    work = frame.sort_values(["Driver", "LapNumber"])
    # Simulate per-driver rolling stats at mid/late race
    from collections import defaultdict

    err_r: dict[str, list[float]] = defaultdict(list)
    err_m: dict[str, list[float]] = defaultdict(list)
    rows = []
    for _, row in work.iterrows():
        drv = str(row["Driver"])
        y = float(row["target"])
        pred_r = predict_from_lap_row(row)
        lag1 = float(row["lag1_pace"]) if pd.notna(row.get("lag1_pace")) else None
        lag2 = float(row["lag2_pace"]) if pd.notna(row.get("lag2_pace")) else None
        pred_m = ma2_from_lags(lag1, lag2)
        if pred_m is None:
            err_r[drv].append(y - pred_r)
            continue
        var_r = rolling_error_variance(err_r[drv][-_BLEND_WINDOW:], min_obs=_BLEND_MIN_OBS)
        var_m = rolling_error_variance(err_m[drv][-_BLEND_WINDOW:], min_obs=_BLEND_MIN_OBS)
        mse_r = float(np.mean(np.square(err_r[drv][-_BLEND_WINDOW:]))) if len(err_r[drv]) >= 3 else 1.0
        mse_m = float(np.mean(np.square(err_m[drv][-_BLEND_WINDOW:]))) if len(err_m[drv]) >= 3 else 1.0
        # mean error (bias)
        bias_r = float(np.mean(err_r[drv][-_BLEND_WINDOW:])) if err_r[drv] else 0.0
        bias_m = float(np.mean(err_m[drv][-_BLEND_WINDOW:])) if err_m[drv] else 0.0
        y_hat_var = inverse_variance_blend(pred_r, pred_m, var_r, var_m)
        y_hat_mse = inverse_variance_blend(pred_r, pred_m, mse_r, mse_m)
        rows.append(
            {
                "abs_err_var_blend": abs(y - y_hat_var),
                "abs_err_mse_blend": abs(y - y_hat_mse),
                "abs_err_r": abs(y - pred_r),
                "abs_err_m": abs(y - pred_m),
                "var_r": var_r,
                "var_m": var_m,
                "mse_r": mse_r,
                "mse_m": mse_m,
                "bias_r": bias_r,
                "bias_m": bias_m,
                "w_r_var": (1 / max(var_r, 1e-6)) / (1 / max(var_r, 1e-6) + 1 / max(var_m, 1e-6)),
                "w_r_mse": (1 / max(mse_r, 1e-6)) / (1 / max(mse_r, 1e-6) + 1 / max(mse_m, 1e-6)),
            }
        )
        err_r[drv].append(y - pred_r)
        err_m[drv].append(y - pred_m)

    df = pd.DataFrame(rows)
    print(f"\n=== {gp} n={len(df)} ===")
    print(
        f"MAE var_blend={df['abs_err_var_blend'].mean():.4f} "
        f"mse_blend={df['abs_err_mse_blend'].mean():.4f} "
        f"physres={df['abs_err_r'].mean():.4f} ma2={df['abs_err_m'].mean():.4f}"
    )
    print(
        f"mean w_physres: var={df['w_r_var'].mean():.3f} mse={df['w_r_mse'].mean():.3f}"
    )
    print(
        f"mean |bias| physres={df['bias_r'].abs().mean():.4f} ma2={df['bias_m'].abs().mean():.4f}"
    )
    print(
        f"mean var_r={df['var_r'].mean():.4f} mse_r={df['mse_r'].mean():.4f} "
        f"(ratio mse/var={ (df['mse_r']/df['var_r'].clip(lower=1e-6)).mean():.2f})"
    )


def main() -> None:
    for gp in ("Australia", "Italy", "Belgium", "Spain", "China", "United States", "Sao Paulo"):
        analyse(gp)


if __name__ == "__main__":
    main()
