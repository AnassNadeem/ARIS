"""XGBoost residual model on top of the physics + tyre predictor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from aris.eval.scoring import mae
from aris.models.cv import race_by_race_folds
from aris.models.features import FEATURE_COLS, build_from_fastf1, feature_matrix

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = _REPO_ROOT / "models" / "residual_xgb.json"

REFERENCE_RACES: list[tuple[int, str]] = [
    (2024, "Bahrain"),
    (2024, "Saudi Arabia"),
    (2024, "Australia"),
    (2024, "Japan"),
    (2024, "Miami"),
    (2023, "Bahrain"),
    (2023, "Belgium"),
    (2023, "Abu Dhabi"),
]


class ResidualModel:
    """Thin wrapper around an XGBoost regressor for lap-time residuals."""

    def __init__(self, booster: xgb.Booster | None = None) -> None:
        self._booster = booster

    @property
    def is_fitted(self) -> bool:
        return self._booster is not None

    def fit(self, frame: pd.DataFrame) -> dict[str, float]:
        """Fit on a combined feature frame; return leave-one-race-out CV MAE."""
        if frame.empty:
            raise ValueError("cannot fit on empty frame")
        fold_maes: list[float] = []
        for train_idx, test_idx in race_by_race_folds(frame, race_col="race_id"):
            train = frame.iloc[train_idx]
            test = frame.iloc[test_idx]
            x_train, y_train, _ = feature_matrix(train)
            x_test, _, y_true = feature_matrix(test)
            booster = _train_booster(x_train, y_train)
            preds = (
                booster.predict(xgb.DMatrix(x_test)) + test["physics_pred"].to_numpy(dtype=float)
            )
            fold_maes.append(mae(y_true, preds))
        # Final fit on all data for the shipped artefact.
        x_all, y_all, _ = feature_matrix(frame)
        self._booster = _train_booster(x_all, y_all)
        return {"cv_mae_mean": float(np.mean(fold_maes)), "cv_mae_std": float(np.std(fold_maes))}

    def predict_residual(self, features: np.ndarray | pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("model not fitted — call fit() or load() first")
        if isinstance(features, pd.DataFrame):
            x = features[FEATURE_COLS].to_numpy(dtype=float)
        else:
            x = features
        return self._booster.predict(xgb.DMatrix(x))  # type: ignore[union-attr]

    def save(self, path: Path | None = None) -> Path:
        if not self.is_fitted:
            raise RuntimeError("model not fitted")
        dest = path or DEFAULT_MODEL_PATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(dest))  # type: ignore[union-attr]
        meta = {"feature_cols": FEATURE_COLS, "version": 1}
        dest.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
        return dest

    @classmethod
    def load(cls, path: Path | None = None) -> ResidualModel:
        src = path or DEFAULT_MODEL_PATH
        if not src.exists():
            raise FileNotFoundError(f"no model at {src} — run train_residual_model() first")
        booster = xgb.Booster()
        booster.load_model(str(src))
        return cls(booster)


def _train_booster(x: np.ndarray, y_residual: np.ndarray) -> xgb.Booster:
    dtrain = xgb.DMatrix(x, label=y_residual)
    params: dict[str, Any] = {
        "objective": "reg:squarederror",
        "max_depth": 4,
        "eta": 0.1,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "seed": 42,
    }
    return xgb.train(params, dtrain, num_boost_round=80)


def load_training_frames(cache_dir: Path | None = None) -> pd.DataFrame:
    """Build and concatenate feature frames for all reference races."""
    import fastf1

    root = cache_dir or (_REPO_ROOT / "fastf1_cache")
    root.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(root))
    frames: list[pd.DataFrame] = []
    for year, gp in REFERENCE_RACES:
        frame = build_from_fastf1(year, gp)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        raise RuntimeError("no training frames built — is fastf1_cache populated?")
    return pd.concat(frames, ignore_index=True)


def train_residual_model(path: Path | None = None) -> tuple[ResidualModel, dict[str, float]]:
    """End-to-end train + save; returns model and CV metrics."""
    frame = load_training_frames()
    model = ResidualModel()
    metrics = model.fit(frame)
    model.save(path)
    return model, metrics
