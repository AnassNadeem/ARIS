"""Re-score Sao Paulo after residual damping."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import (  # noqa: E402
    damp_residual_toward_pace,
    predict_blended_frame,
    predict_from_lap_row,
    reset_model_cache,
)
from aris.models.residual import ResidualModel  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))
reset_model_cache()
frame = build_from_fastf1(2024, "Sao Paulo")
target = frame["target"].to_numpy(dtype=float)
phys = frame["physics_pred"].to_numpy(dtype=float)

model = ResidualModel.load()
raw_res = model.predict_residual(frame)
damped = np.array(
    [
        damp_residual_toward_pace(
            float(phys[i]),
            float(frame.iloc[i]["lag1_pace"]) if np.isfinite(frame.iloc[i]["lag1_pace"]) else None,
            float(raw_res[i]),
        )
        for i in range(len(frame))
    ]
)
phys_res = phys + damped
blended = predict_blended_frame(frame)

def mae(a, b):
    return float(np.mean(np.abs(a - b)))

aimed = 1.5 * 1.113691
print(f"phys MAE={mae(phys, target):.4f}")
print(f"phys+raw_res MAE={mae(phys + raw_res, target):.4f}")
print(f"phys+damped_res MAE={mae(phys_res, target):.4f}")
print(f"blend MAE={mae(blended, target):.4f}  aimed={aimed:.4f}  "
      f"{'PASS' if mae(blended, target) <= aimed else 'MISS'}")
print(f"raw_res mean={raw_res.mean():.3f} damped mean={damped.mean():.3f}")
print(f"Phase D blend was 2.092; E2 was 3.121")
