"""Recheck miss races after MSE blend fix."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import predict_blended_frame, reset_model_cache  # noqa: E402
from aris.tracks import clear_track_config_cache  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))

# aimed uses live MA2 from E3.4 diagnosis where available
RACES = [
    ("Australia", 0.4632),
    ("China", 0.3756),
    ("Spain", 0.4761),
    ("Belgium", 0.4259),
    ("Italy", 0.4535),
    ("United States", 0.3931),
    ("Sao Paulo", 1.1137),
    ("Netherlands", 0.427),
]

for gp, ma2 in RACES:
    clear_track_config_cache()
    reset_model_cache()
    frame = build_from_fastf1(2024, gp)
    y = frame["target"].to_numpy(dtype=float)
    p = predict_blended_frame(frame)
    mae = float(np.mean(np.abs(y - p)))
    aimed = 1.5 * ma2
    flag = "PASS" if mae <= aimed else "MISS"
    print(f"{gp:<16} blend={mae:.4f} aimed={aimed:.4f} {flag}")
