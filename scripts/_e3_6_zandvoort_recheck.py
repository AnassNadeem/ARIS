"""E3.6 Zandvoort 2024+2025 recheck after all E3 fixes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.eval.baseline import moving_average_baseline  # noqa: E402
from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import predict_blended_frame, predict_from_lap_row, reset_model_cache  # noqa: E402
from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402
from aris.tracks import clear_track_config_cache  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))


def mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def score(year: int) -> dict:
    clear_track_config_cache()
    reset_model_cache()
    frame = build_from_fastf1(year, "Netherlands")
    y = frame["target"].to_numpy(dtype=float)
    phys = frame["physics_pred"].to_numpy(dtype=float)
    phys_res = np.array([predict_from_lap_row(r) for _, r in frame.iterrows()])
    blend = predict_blended_frame(frame)
    session = fastf1.get_session(year, "Netherlands", "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    ma2 = moving_average_baseline(clean, window=2).reindex(clean.index)
    m = ma2.notna()
    ma2_mae = mae(clean.loc[m, "LapTimeS"], ma2.loc[m])
    aimed = 1.5 * ma2_mae
    return {
        "year": year,
        "ma2": round(ma2_mae, 4),
        "aimed": round(aimed, 4),
        "phys": round(mae(phys, y), 4),
        "phys_res": round(mae(phys_res, y), 4),
        "blend": round(mae(blend, y), 4),
        "pass": bool(mae(blend, y) <= aimed),
        "e2_blend_ref": 0.555 if year == 2024 else 0.679,
        "e2_aimed_ref": 0.640 if year == 2024 else 0.626,
    }


results = [score(2024), score(2025)]
path = _ROOT / "results" / "e3_6_zandvoort.json"
path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
print(f"Wrote {path}")
