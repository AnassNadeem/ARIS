"""Phase C.1c — LORO-CV hyperparameter tune + fit-all residual refit.

Selection criterion is LORO-CV MAE only (held-out must stay untouched by
tuning decisions). Uses checkpointed frames under results/train_frames/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

from aris.models.predict import reset_model_cache  # noqa: E402
from aris.models.residual import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    DEFAULT_XGB_PARAMS,
    train_residual_model_from_frame,
    tune_hyperparams,
)

_FRAMES_DIR = _REPO / "results" / "train_frames"
_RESULTS = _REPO / "results"


def load_checkpointed_frames() -> pd.DataFrame:
    paths = sorted(_FRAMES_DIR.glob("*.parquet"))
    if not paths:
        raise RuntimeError(f"no checkpointed frames in {_FRAMES_DIR}")
    frames = [pd.read_parquet(p) for p in paths]
    combined = pd.concat(frames, ignore_index=True)
    print(
        f"Loaded {len(paths)} race frames / {len(combined)} laps from {_FRAMES_DIR}",
        flush=True,
    )
    return combined


def main() -> None:
    frame = load_checkpointed_frames()
    best, all_rows = tune_hyperparams(frame, screen_stride=5)
    _RESULTS.mkdir(parents=True, exist_ok=True)
    out = _RESULTS / "residual-tune-c1c.json"
    out.write_text(json.dumps({"best": best, "runs": all_rows}, indent=2), encoding="utf-8")
    print(f"Wrote {out}", flush=True)

    params = dict(DEFAULT_XGB_PARAMS)
    params["max_depth"] = int(best["max_depth"])
    params["eta"] = float(best["eta"])
    # Backup pre-tune artefact once.
    backup = DEFAULT_MODEL_PATH.with_name("residual_xgb.phaseB.json")
    if DEFAULT_MODEL_PATH.exists() and not backup.exists():
        backup.write_bytes(DEFAULT_MODEL_PATH.read_bytes())
        meta = DEFAULT_MODEL_PATH.with_suffix(".meta.json")
        if meta.exists():
            meta.with_name("residual_xgb.phaseB.meta.json").write_text(
                meta.read_text(encoding="utf-8"), encoding="utf-8"
            )
        print(f"Backed up Phase B model -> {backup}", flush=True)

    print("\nFit-all with selected hyperparameters...", flush=True)
    model, metrics = train_residual_model_from_frame(
        frame,
        path=DEFAULT_MODEL_PATH,
        xgb_params=params,
        num_boost_round=int(best["num_boost_round"]),
    )
    reset_model_cache()
    print(
        f"Shipped model CV MAE: {metrics['cv_mae_mean']:.3f} "
        f"+/- {metrics['cv_mae_std']:.3f} s",
        flush=True,
    )
    print(f"Saved {DEFAULT_MODEL_PATH} ({model.is_fitted})", flush=True)


if __name__ == "__main__":
    main()
