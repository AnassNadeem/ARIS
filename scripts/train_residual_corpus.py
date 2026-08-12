"""Checkpointed training-frame builder + residual refit for Phase B Block 3.

Saves per-race frames to results/train_frames/ so a rate-limit interrupt does
not throw away hours of FastF1 downloads. Then runs the existing LORO-CV +
fit-all procedure from ResidualModel.fit.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

import aris  # noqa: F401
import fastf1
from fastf1.exceptions import RateLimitExceededError

from aris.models.features import build_from_fastf1
from aris.models.predict import reset_model_cache
from aris.models.residual import DEFAULT_MODEL_PATH, REFERENCE_RACES, ResidualModel
from aris.tracks import clear_track_config_cache

_REPO = Path(__file__).resolve().parents[1]
_FRAMES_DIR = _REPO / "results" / "train_frames"
_CACHE = _REPO / "fastf1_cache"


def _frame_path(year: int, gp: str) -> Path:
    safe = gp.replace(" ", "_").replace("/", "_")
    return _FRAMES_DIR / f"{year}_{safe}.parquet"


def build_missing_frames(
    *,
    max_rate_limit_sleep_s: int = 3600,
    force_rebuild: bool = False,
) -> tuple[int, int, int]:
    """Load any REFERENCE_RACES not yet checkpointed. Returns (ok, skipped, failed)."""
    _FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(_CACHE))
    clear_track_config_cache()

    ok = skipped = failed = 0
    n = len(REFERENCE_RACES)
    for i, (year, gp) in enumerate(REFERENCE_RACES, start=1):
        dest = _frame_path(year, gp)
        if dest.exists() and not force_rebuild:
            skipped += 1
            print(f"[{i}/{n}] CACHED {year} {gp}", flush=True)
            continue
        label = f"{year} {gp}"
        attempts = 0
        while True:
            attempts += 1
            try:
                frame = build_from_fastf1(year, gp)
                if frame.empty:
                    failed += 1
                    print(f"[{i}/{n}] EMPTY {label}", flush=True)
                else:
                    frame.to_parquet(dest, index=False)
                    ok += 1
                    verb = "REBUILT" if force_rebuild and dest.exists() else "OK"
                    print(f"[{i}/{n}] {verb} {label}: {len(frame)} laps -> {dest.name}", flush=True)
                break
            except RateLimitExceededError:
                # Client sliding window is 500 calls / 3600s — wait for a full window.
                wait_s = min(max_rate_limit_sleep_s, 900 * attempts)
                print(
                    f"[{i}/{n}] rate-limited on {label}; sleeping {wait_s}s "
                    f"(attempt {attempts})",
                    flush=True,
                )
                time.sleep(wait_s)
                if attempts >= 4:
                    failed += 1
                    print(f"[{i}/{n}] FAIL {label}: rate limit", flush=True)
                    break
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"[{i}/{n}] FAIL {label}: {exc}", flush=True)
                break
    return ok, skipped, failed


def load_checkpointed_frames() -> pd.DataFrame:
    paths = sorted(_FRAMES_DIR.glob("*.parquet"))
    if not paths:
        raise RuntimeError(f"no checkpointed frames in {_FRAMES_DIR}")
    frames = [pd.read_parquet(p) for p in paths]
    combined = pd.concat(frames, ignore_index=True)
    print(
        f"Loaded {len(paths)} race frames / {len(combined)} laps "
        f"from {_FRAMES_DIR}",
        flush=True,
    )
    return combined


def train_from_checkpoints(path: Path | None = None) -> dict[str, float]:
    frame = load_checkpointed_frames()
    model = ResidualModel()
    metrics = model.fit(frame)
    model.save(path or DEFAULT_MODEL_PATH)
    reset_model_cache()
    print(f"Saved model -> {path or DEFAULT_MODEL_PATH}", flush=True)
    print(f"CV MAE: {metrics['cv_mae_mean']:.3f} +/- {metrics['cv_mae_std']:.3f} s", flush=True)
    return metrics


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--train-only", action="store_true")
    parser.add_argument(
        "--rebuild-all",
        action="store_true",
        help="Rebuild every REFERENCE_RACES frame (ignore existing parquet cache)",
    )
    args = parser.parse_args()
    if not args.train_only:
        ok, skipped, failed = build_missing_frames(force_rebuild=args.rebuild_all)
        print(f"build done: ok={ok} skipped={skipped} failed={failed}", flush=True)
    if not args.build_only:
        train_from_checkpoints()


if __name__ == "__main__":
    main()