"""E3.3 — São Paulo residual overshoot diagnosis."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.models.features import FEATURE_COLS, build_from_fastf1  # noqa: E402
from aris.models.predict import predict_blended_frame, reset_model_cache  # noqa: E402
from aris.models.residual import DEFAULT_MODEL_PATH, ResidualModel  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))


def _mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def score_with_model(frame: pd.DataFrame, model_path: Path) -> dict:
    reset_model_cache()
    model = ResidualModel.load(model_path)
    phys = frame["physics_pred"].to_numpy(dtype=float)
    target = frame["target"].to_numpy(dtype=float)
    true_res = target - phys
    pred_res = model.predict_residual(frame)
    phys_res = phys + pred_res
    # Temporarily point DEFAULT by monkeypatching predict cache — use direct blend
    # via phys+res vs build blended with loaded model:
    from aris.models import predict as pred_mod

    pred_mod._MODEL = model  # type: ignore[attr-defined]
    blended = predict_blended_frame(frame)
    return {
        "model": str(model_path.name),
        "n": len(frame),
        "phys_mae": round(_mae(phys, target), 4),
        "phys_res_mae": round(_mae(phys_res, target), 4),
        "blend_mae": round(_mae(blended, target), 4),
        "true_residual_mean": round(float(np.mean(true_res)), 4),
        "true_residual_mae": round(float(np.mean(np.abs(true_res))), 4),
        "pred_residual_mean": round(float(np.mean(pred_res)), 4),
        "pred_residual_mae": round(float(np.mean(np.abs(pred_res))), 4),
        "pred_residual_p50": round(float(np.median(pred_res)), 4),
        "pred_residual_p90_abs": round(float(np.percentile(np.abs(pred_res), 90)), 4),
        # Overshoot: when |pred_res| > |true_res| and wrong direction or too large
        "frac_pred_abs_gt_true_abs": round(
            float(np.mean(np.abs(pred_res) > np.abs(true_res))), 4
        ),
        "frac_phys_already_within_1s": round(float(np.mean(np.abs(true_res) < 1.0)), 4),
        "mae_when_phys_within_1s_phys": None,
        "mae_when_phys_within_1s_physres": None,
        "mae_when_phys_within_1s_pred_res_mean_abs": None,
    }


def enrich(stats: dict, frame: pd.DataFrame, model_path: Path) -> dict:
    model = ResidualModel.load(model_path)
    phys = frame["physics_pred"].to_numpy(dtype=float)
    target = frame["target"].to_numpy(dtype=float)
    true_res = target - phys
    pred_res = model.predict_residual(frame)
    mask = np.abs(true_res) < 1.0
    if mask.any():
        stats["mae_when_phys_within_1s_phys"] = round(_mae(phys[mask], target[mask]), 4)
        stats["mae_when_phys_within_1s_physres"] = round(
            _mae(phys[mask] + pred_res[mask], target[mask]), 4
        )
        stats["mae_when_phys_within_1s_pred_res_mean_abs"] = round(
            float(np.mean(np.abs(pred_res[mask]))), 4
        )
        stats["n_phys_within_1s"] = int(mask.sum())
    # Bucket by |physics error|
    buckets = []
    for lo, hi in [(0, 1), (1, 2), (2, 4), (4, 8), (8, 100)]:
        m = (np.abs(true_res) >= lo) & (np.abs(true_res) < hi)
        if not m.any():
            continue
        buckets.append(
            {
                "abs_phys_err": f"[{lo},{hi})",
                "n": int(m.sum()),
                "phys_mae": round(_mae(phys[m], target[m]), 4),
                "phys_res_mae": round(_mae(phys[m] + pred_res[m], target[m]), 4),
                "pred_res_mean_abs": round(float(np.mean(np.abs(pred_res[m]))), 4),
                "true_res_mean_abs": round(float(np.mean(np.abs(true_res[m]))), 4),
            }
        )
    stats["buckets"] = buckets
    # Does the model see physics_pred?
    stats["physics_pred_in_features"] = "physics_pred" in FEATURE_COLS
    stats["feature_cols"] = list(FEATURE_COLS)
    # Correlation pred_res vs true_res
    if len(true_res) > 2:
        stats["corr_pred_true_res"] = round(
            float(np.corrcoef(pred_res, true_res)[0, 1]), 4
        )
    return stats


def main() -> None:
    print("Building 2024 Sao Paulo feature frame...", flush=True)
    frame = build_from_fastf1(2024, "Sao Paulo")
    print(f"n={len(frame)} phys_med={frame['physics_pred'].median():.2f} "
          f"tgt_med={frame['target'].median():.2f}", flush=True)

    pre = _ROOT / "models" / "residual_xgb.pre_e2.json"
    cur = DEFAULT_MODEL_PATH
    results = {}
    for path, key in [(pre, "pre_e2"), (cur, "e2")]:
        if not path.exists():
            results[key] = {"error": f"missing {path}"}
            continue
        s = score_with_model(frame, path)
        s = enrich(s, frame, path)
        results[key] = s
        print(json.dumps(s, indent=2), flush=True)

    # Corpus-wide: how often is phys already within 1s on train frames?
    print("\nScanning train frames for phys-closeness vs Sao Paulo...", flush=True)
    rows = []
    for p in sorted((_ROOT / "results" / "train_frames").glob("*.parquet")):
        df = pd.read_parquet(p)
        if "physics_pred" not in df.columns or "target" not in df.columns:
            continue
        err = (df["target"] - df["physics_pred"]).abs()
        rows.append(
            {
                "race": p.stem,
                "phys_mae": float(err.mean()),
                "frac_within_1s": float((err < 1).mean()),
                "frac_within_2s": float((err < 2).mean()),
                "n": len(df),
            }
        )
    corp = pd.DataFrame(rows).sort_values("phys_mae")
    print("Best 8 train races by phys MAE:")
    print(corp.head(8).to_string(index=False))
    print("\nSao Paulo-like names:")
    print(corp[corp["race"].str.contains("Paulo|Brazil", case=False, na=False)].to_string(index=False))
    print(f"\nCorpus median phys_mae={corp['phys_mae'].median():.3f} "
          f"p10={corp['phys_mae'].quantile(0.1):.3f}")
    sp_phys = float((frame["target"] - frame["physics_pred"]).abs().mean())
    print(f"2024 Sao Paulo phys_mae={sp_phys:.3f} "
          f"(percentile vs train: {(corp['phys_mae'] < sp_phys).mean()*100:.1f}th better-than)")

    out = {
        "sao_paulo_2024": results,
        "train_phys_mae_median": float(corp["phys_mae"].median()),
        "train_phys_mae_p10": float(corp["phys_mae"].quantile(0.1)),
        "sao_paulo_phys_mae": sp_phys,
    }
    path = _ROOT / "results" / "e3_3_sao_paulo_diagnosis.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
