"""E2.5 — rebuild physics_pred on cached train frames, then LORO-CV refit.

Does NOT re-fetch FastF1. Recomputes bicycle physics_pred (+ residual target)
from existing feature columns using the current track YAMLs (geometry +
compound_slopes). Then runs the existing ResidualModel.fit LORO-CV + fit-all.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
from aris.models.features import physics_prediction_row  # noqa: E402
from aris.models.predict import reset_model_cache  # noqa: E402
from aris.models.residual import DEFAULT_MODEL_PATH, ResidualModel  # noqa: E402
from aris.tracks import clear_track_config_cache, load_track_config  # noqa: E402

_FRAMES = _ROOT / "results" / "train_frames"
_CODE_TO_COMPOUND = {
    0: "SOFT",
    1: "MEDIUM",
    2: "HARD",
    3: "INTERMEDIATE",
    4: "WET",
}


def _gp_from_filename(path: Path) -> str:
    # 2018_Abu_Dhabi_Grand_Prix.parquet → Abu Dhabi Grand Prix
    stem = path.stem
    parts = stem.split("_", 1)
    if len(parts) < 2:
        raise ValueError(f"unexpected frame name {path.name}")
    return parts[1].replace("_", " ")


def rebuild_frame(path: Path) -> tuple[int, float, float]:
    gp = _gp_from_filename(path)
    cfg = load_track_config(gp)
    track = cfg.load_physics()
    df = pd.read_parquet(path)
    old_med = float(df["physics_pred"].median())

    def _row_phys(row: pd.Series) -> float:
        compound = _CODE_TO_COMPOUND.get(int(row["compound_code"]), "MEDIUM")
        fake = pd.Series(
            {
                "fuel_kg": float(row["fuel_kg"]),
                "pit_lap": False,
                "compound": compound,
                "tyre_life": int(row["tyre_life"]),
            }
        )
        return physics_prediction_row(fake, track=track)

    df["physics_pred"] = df.apply(_row_phys, axis=1)
    df["residual"] = df["target"] - df["physics_pred"]
    new_med = float(df["physics_pred"].median())
    df.to_parquet(path, index=False)
    return len(df), old_med, new_med


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-only", action="store_true")
    parser.add_argument("--train-only", action="store_true")
    parser.add_argument(
        "--backup-model",
        action="store_true",
        help="Copy current residual artefact to residual_xgb.pre_e2.json before overwrite",
    )
    args = parser.parse_args()

    clear_track_config_cache()
    reset_model_cache()

    if not args.train_only:
        paths = sorted(_FRAMES.glob("*.parquet"))
        if not paths:
            raise SystemExit(f"no frames in {_FRAMES}")
        print(f"Rebuilding physics_pred on {len(paths)} frames...", flush=True)
        for i, path in enumerate(paths, start=1):
            n, old_m, new_m = rebuild_frame(path)
            print(
                f"[{i}/{len(paths)}] {path.name}: n={n} phys_med {old_m:.2f} -> {new_m:.2f} "
                f"(delta={new_m - old_m:+.2f})",
                flush=True,
            )

    if args.rebuild_only:
        return

    if args.backup_model and DEFAULT_MODEL_PATH.exists():
        bak = DEFAULT_MODEL_PATH.with_name("residual_xgb.pre_e2.json")
        shutil.copy2(DEFAULT_MODEL_PATH, bak)
        meta = DEFAULT_MODEL_PATH.with_suffix(".meta.json")
        if meta.exists():
            shutil.copy2(meta, bak.with_suffix(".meta.json"))
        print(f"Backed up model -> {bak}", flush=True)

    frames = [pd.read_parquet(p) for p in sorted(_FRAMES.glob("*.parquet"))]
    combined = pd.concat(frames, ignore_index=True)
    print(f"Training on {len(frames)} races / {len(combined)} laps", flush=True)
    model = ResidualModel()
    metrics = model.fit(combined)
    model.save(DEFAULT_MODEL_PATH)
    reset_model_cache()
    print(f"Saved {DEFAULT_MODEL_PATH}", flush=True)
    print(
        f"CV MAE: {metrics['cv_mae_mean']:.3f} +/- {metrics['cv_mae_std']:.3f} s",
        flush=True,
    )


if __name__ == "__main__":
    main()
