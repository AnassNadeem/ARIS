"""Test MA(1) fallback when lag2 missing — China impact."""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

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


def score(gp: str, *, use_ma1: bool) -> float:
    reset_model_cache()
    frame = build_from_fastf1(2024, gp)
    work = frame.sort_values(["Driver", "LapNumber"])
    err_r: dict[str, list[float]] = defaultdict(list)
    err_m: dict[str, list[float]] = defaultdict(list)
    abs_errs = []
    for _, row in work.iterrows():
        drv = str(row["Driver"])
        y = float(row["target"])
        pred_r = predict_from_lap_row(row)
        lag1 = float(row["lag1_pace"]) if pd.notna(row.get("lag1_pace")) else None
        lag2 = float(row["lag2_pace"]) if pd.notna(row.get("lag2_pace")) else None
        pred_m = ma2_from_lags(lag1, lag2)
        if pred_m is None and use_ma1 and lag1 is not None and np.isfinite(lag1):
            pred_m = lag1
        if pred_m is None:
            abs_errs.append(abs(y - pred_r))
            err_r[drv].append(y - pred_r)
            continue
        y_hat = inverse_variance_blend(
            pred_r,
            pred_m,
            rolling_error_variance(err_r[drv][-_BLEND_WINDOW:], min_obs=_BLEND_MIN_OBS),
            rolling_error_variance(err_m[drv][-_BLEND_WINDOW:], min_obs=_BLEND_MIN_OBS),
        )
        abs_errs.append(abs(y - y_hat))
        err_r[drv].append(y - pred_r)
        err_m[drv].append(y - pred_m)
    return float(np.mean(abs_errs))


for gp, ma2 in [
    ("China", 0.3756),
    ("Australia", 0.4632),
    ("Netherlands", 0.427),
    ("Sao Paulo", 1.1137),
    ("Italy", 0.4535),
]:
    a = score(gp, use_ma1=False)
    b = score(gp, use_ma1=True)
    aimed = 1.5 * ma2
    print(
        f"{gp:<14} no_ma1={a:.4f} with_ma1={b:.4f} aimed={aimed:.4f} "
        f"delta={b-a:+.4f} {'PASS' if b<=aimed else 'MISS'}"
    )
