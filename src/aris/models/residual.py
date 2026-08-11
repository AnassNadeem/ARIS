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

# Full 2018–2023 race corpus (125 sessions). Held-out eval is 2024-only and
# disjoint by year. Expanded in Phase B from the original 8-race set.
REFERENCE_RACES: list[tuple[int, str]] = [
    (2018, "Australian Grand Prix"),
    (2018, "Bahrain Grand Prix"),
    (2018, "Chinese Grand Prix"),
    (2018, "Azerbaijan Grand Prix"),
    (2018, "Spanish Grand Prix"),
    (2018, "Monaco Grand Prix"),
    (2018, "Canadian Grand Prix"),
    (2018, "French Grand Prix"),
    (2018, "Austrian Grand Prix"),
    (2018, "British Grand Prix"),
    (2018, "German Grand Prix"),
    (2018, "Hungarian Grand Prix"),
    (2018, "Belgian Grand Prix"),
    (2018, "Italian Grand Prix"),
    (2018, "Singapore Grand Prix"),
    (2018, "Russian Grand Prix"),
    (2018, "Japanese Grand Prix"),
    (2018, "United States Grand Prix"),
    (2018, "Mexican Grand Prix"),
    (2018, "Brazilian Grand Prix"),
    (2018, "Abu Dhabi Grand Prix"),
    (2019, "Australian Grand Prix"),
    (2019, "Bahrain Grand Prix"),
    (2019, "Chinese Grand Prix"),
    (2019, "Azerbaijan Grand Prix"),
    (2019, "Spanish Grand Prix"),
    (2019, "Monaco Grand Prix"),
    (2019, "Canadian Grand Prix"),
    (2019, "French Grand Prix"),
    (2019, "Austrian Grand Prix"),
    (2019, "British Grand Prix"),
    (2019, "German Grand Prix"),
    (2019, "Hungarian Grand Prix"),
    (2019, "Belgian Grand Prix"),
    (2019, "Italian Grand Prix"),
    (2019, "Singapore Grand Prix"),
    (2019, "Russian Grand Prix"),
    (2019, "Japanese Grand Prix"),
    (2019, "Mexican Grand Prix"),
    (2019, "United States Grand Prix"),
    (2019, "Brazilian Grand Prix"),
    (2019, "Abu Dhabi Grand Prix"),
    (2020, "Austrian Grand Prix"),
    (2020, "Styrian Grand Prix"),
    (2020, "Hungarian Grand Prix"),
    (2020, "British Grand Prix"),
    (2020, "70th Anniversary Grand Prix"),
    (2020, "Spanish Grand Prix"),
    (2020, "Belgian Grand Prix"),
    (2020, "Italian Grand Prix"),
    (2020, "Tuscan Grand Prix"),
    (2020, "Russian Grand Prix"),
    (2020, "Eifel Grand Prix"),
    (2020, "Portuguese Grand Prix"),
    (2020, "Emilia Romagna Grand Prix"),
    (2020, "Turkish Grand Prix"),
    (2020, "Bahrain Grand Prix"),
    (2020, "Sakhir Grand Prix"),
    (2020, "Abu Dhabi Grand Prix"),
    (2021, "Bahrain Grand Prix"),
    (2021, "Emilia Romagna Grand Prix"),
    (2021, "Portuguese Grand Prix"),
    (2021, "Spanish Grand Prix"),
    (2021, "Monaco Grand Prix"),
    (2021, "Azerbaijan Grand Prix"),
    (2021, "French Grand Prix"),
    (2021, "Styrian Grand Prix"),
    (2021, "Austrian Grand Prix"),
    (2021, "British Grand Prix"),
    (2021, "Hungarian Grand Prix"),
    (2021, "Belgian Grand Prix"),
    (2021, "Dutch Grand Prix"),
    (2021, "Italian Grand Prix"),
    (2021, "Russian Grand Prix"),
    (2021, "Turkish Grand Prix"),
    (2021, "United States Grand Prix"),
    (2021, "Mexico City Grand Prix"),
    (2021, "São Paulo Grand Prix"),
    (2021, "Qatar Grand Prix"),
    (2021, "Saudi Arabian Grand Prix"),
    (2021, "Abu Dhabi Grand Prix"),
    (2022, "Bahrain Grand Prix"),
    (2022, "Saudi Arabian Grand Prix"),
    (2022, "Australian Grand Prix"),
    (2022, "Emilia Romagna Grand Prix"),
    (2022, "Miami Grand Prix"),
    (2022, "Spanish Grand Prix"),
    (2022, "Monaco Grand Prix"),
    (2022, "Azerbaijan Grand Prix"),
    (2022, "Canadian Grand Prix"),
    (2022, "British Grand Prix"),
    (2022, "Austrian Grand Prix"),
    (2022, "French Grand Prix"),
    (2022, "Hungarian Grand Prix"),
    (2022, "Belgian Grand Prix"),
    (2022, "Dutch Grand Prix"),
    (2022, "Italian Grand Prix"),
    (2022, "Singapore Grand Prix"),
    (2022, "Japanese Grand Prix"),
    (2022, "United States Grand Prix"),
    (2022, "Mexico City Grand Prix"),
    (2022, "São Paulo Grand Prix"),
    (2022, "Abu Dhabi Grand Prix"),
    (2023, "Bahrain Grand Prix"),
    (2023, "Saudi Arabian Grand Prix"),
    (2023, "Australian Grand Prix"),
    (2023, "Azerbaijan Grand Prix"),
    (2023, "Miami Grand Prix"),
    (2023, "Monaco Grand Prix"),
    (2023, "Spanish Grand Prix"),
    (2023, "Canadian Grand Prix"),
    (2023, "Austrian Grand Prix"),
    (2023, "British Grand Prix"),
    (2023, "Hungarian Grand Prix"),
    (2023, "Belgian Grand Prix"),
    (2023, "Dutch Grand Prix"),
    (2023, "Italian Grand Prix"),
    (2023, "Singapore Grand Prix"),
    (2023, "Japanese Grand Prix"),
    (2023, "Qatar Grand Prix"),
    (2023, "United States Grand Prix"),
    (2023, "Mexico City Grand Prix"),
    (2023, "São Paulo Grand Prix"),
    (2023, "Las Vegas Grand Prix"),
    (2023, "Abu Dhabi Grand Prix"),
]

# Training-time vs replay-time leakage (intentional distinction — do not "fix"):
# ``train_residual_model`` / ``ResidualModel.fit`` train on whole races from
# REFERENCE_RACES. Within each race, features are causal (lags use shift), but
# the final booster is fit on all reference races after leave-one-race-out CV.
# That is standard offline supervised learning, not a mid-race replay cutoff.
# Replay-time leakage (seeing future sectors/laps during a live tick) is a
# separate class of bug handled in field/standings and feature builders.
# Flagged for Anas's review in Phase A rather than changed here.


# Default booster knobs (Phase B). Phase C.1c may overwrite via tune_hyperparams.
DEFAULT_XGB_PARAMS: dict[str, Any] = {
    "objective": "reg:squarederror",
    "max_depth": 4,
    "eta": 0.1,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "seed": 42,
}
DEFAULT_NUM_BOOST_ROUND = 80
DEFAULT_EARLY_STOPPING_ROUNDS = 20

# Small Phase C.1c search space — pick by LORO-CV MAE only (held-out untouched).
TUNE_GRID: list[dict[str, Any]] = [
    {"max_depth": 3, "eta": 0.05, "num_boost_round": 200},
    {"max_depth": 3, "eta": 0.1, "num_boost_round": 150},
    {"max_depth": 4, "eta": 0.05, "num_boost_round": 200},
    {"max_depth": 4, "eta": 0.1, "num_boost_round": 80},  # Phase B baseline
    {"max_depth": 4, "eta": 0.2, "num_boost_round": 100},
    {"max_depth": 6, "eta": 0.05, "num_boost_round": 200},
    {"max_depth": 6, "eta": 0.1, "num_boost_round": 120},
    {"max_depth": 5, "eta": 0.08, "num_boost_round": 150},
]


class ResidualModel:
    """Thin wrapper around an XGBoost regressor for lap-time residuals."""

    def __init__(
        self,
        booster: xgb.Booster | None = None,
        *,
        xgb_params: dict[str, Any] | None = None,
        num_boost_round: int | None = None,
    ) -> None:
        self._booster = booster
        self._xgb_params = dict(xgb_params or DEFAULT_XGB_PARAMS)
        self._num_boost_round = (
            DEFAULT_NUM_BOOST_ROUND if num_boost_round is None else int(num_boost_round)
        )

    @property
    def is_fitted(self) -> bool:
        return self._booster is not None

    def fit(self, frame: pd.DataFrame) -> dict[str, float]:
        """Fit on a combined feature frame; return leave-one-race-out CV MAE."""
        if frame.empty:
            raise ValueError("cannot fit on empty frame")
        fold_maes: list[float] = []
        n_races = frame["race_id"].nunique()
        print(f"LORO-CV over {n_races} races / {len(frame)} laps...")
        for i, (train_idx, test_idx) in enumerate(
            race_by_race_folds(frame, race_col="race_id"), start=1
        ):
            train = frame.iloc[train_idx]
            test = frame.iloc[test_idx]
            x_train, y_train, _ = feature_matrix(train)
            x_test, _, y_true = feature_matrix(test)
            # Early-stop against a race-holdout from *train* (not the LORO test
            # fold) so fold MAE stays honest.
            booster = _train_booster(
                x_train,
                y_train,
                params=self._xgb_params,
                num_boost_round=self._num_boost_round,
                early_stopping_rounds=DEFAULT_EARLY_STOPPING_ROUNDS,
                eval_fraction=0.1,
            )
            preds = (
                booster.predict(xgb.DMatrix(x_test)) + test["physics_pred"].to_numpy(dtype=float)
            )
            fold_mae = mae(y_true, preds)
            fold_maes.append(fold_mae)
            if i == 1 or i % 10 == 0 or i == n_races:
                print(f"  fold {i}/{n_races}: MAE={fold_mae:.3f} s")
        # Final fit on all data for the shipped artefact.
        x_all, y_all, _ = feature_matrix(frame)
        self._booster = _train_booster(
            x_all,
            y_all,
            params=self._xgb_params,
            num_boost_round=self._num_boost_round,
            early_stopping_rounds=DEFAULT_EARLY_STOPPING_ROUNDS,
            eval_fraction=0.1,
        )
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
        meta = {
            "feature_cols": FEATURE_COLS,
            "version": 1,
            "xgb_params": self._xgb_params,
            "num_boost_round": self._num_boost_round,
        }
        dest.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
        return dest

    @classmethod
    def load(cls, path: Path | None = None) -> ResidualModel:
        src = path or DEFAULT_MODEL_PATH
        if not src.exists():
            raise FileNotFoundError(f"no model at {src} — run train_residual_model() first")
        booster = xgb.Booster()
        booster.load_model(str(src))
        meta_path = src.with_suffix(".meta.json")
        params = dict(DEFAULT_XGB_PARAMS)
        n_rounds = DEFAULT_NUM_BOOST_ROUND
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if isinstance(meta.get("xgb_params"), dict):
                params.update(meta["xgb_params"])
            if meta.get("num_boost_round") is not None:
                n_rounds = int(meta["num_boost_round"])
        return cls(booster, xgb_params=params, num_boost_round=n_rounds)


def _train_booster(
    x: np.ndarray,
    y_residual: np.ndarray,
    *,
    params: dict[str, Any] | None = None,
    num_boost_round: int | None = None,
    early_stopping_rounds: int | None = None,
    eval_fraction: float = 0.0,
) -> xgb.Booster:
    """Train a booster; optional early stopping on a trailing fraction of rows."""
    cfg = dict(DEFAULT_XGB_PARAMS)
    if params:
        cfg.update({k: v for k, v in params.items() if k != "num_boost_round"})
    rounds = DEFAULT_NUM_BOOST_ROUND if num_boost_round is None else int(num_boost_round)

    n = len(y_residual)
    use_es = (
        early_stopping_rounds is not None
        and early_stopping_rounds > 0
        and 0.0 < eval_fraction < 0.5
        and n >= 50
    )
    if use_es:
        cut = max(1, int(n * (1.0 - eval_fraction)))
        # Trailing slice as eval — frames are race-concatenated so this is a
        # soft race holdout, not a random shuffle (keeps causal order intact).
        dtrain = xgb.DMatrix(x[:cut], label=y_residual[:cut])
        deval = xgb.DMatrix(x[cut:], label=y_residual[cut:])
        return xgb.train(
            cfg,
            dtrain,
            num_boost_round=rounds,
            evals=[(deval, "eval")],
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=False,
        )
    dtrain = xgb.DMatrix(x, label=y_residual)
    return xgb.train(cfg, dtrain, num_boost_round=rounds)


def loro_cv_mae(
    frame: pd.DataFrame,
    *,
    params: dict[str, Any],
    num_boost_round: int,
    early_stopping_rounds: int = DEFAULT_EARLY_STOPPING_ROUNDS,
    fold_stride: int = 1,
    quiet: bool = False,
) -> dict[str, float]:
    """Leave-one-race-out CV MAE for one hyperparameter configuration.

    ``fold_stride`` > 1 evaluates every Nth race (faster screening); final
    selection should use stride=1 on the shortlisted configs.
    """
    fold_maes: list[float] = []
    folds = list(race_by_race_folds(frame, race_col="race_id"))
    selected = list(enumerate(folds, start=1))
    if fold_stride > 1:
        selected = selected[::fold_stride]
    n_eval = len(selected)
    for j, (i, (train_idx, test_idx)) in enumerate(selected, start=1):
        train = frame.iloc[train_idx]
        test = frame.iloc[test_idx]
        x_train, y_train, _ = feature_matrix(train)
        x_test, _, y_true = feature_matrix(test)
        booster = _train_booster(
            x_train,
            y_train,
            params=params,
            num_boost_round=num_boost_round,
            early_stopping_rounds=early_stopping_rounds,
            eval_fraction=0.1,
        )
        preds = booster.predict(xgb.DMatrix(x_test)) + test["physics_pred"].to_numpy(dtype=float)
        fold_maes.append(mae(y_true, preds))
        if not quiet and (j == 1 or j % 5 == 0 or j == n_eval):
            print(
                f"    fold {i}/{len(folds)} ({j}/{n_eval}): MAE={fold_maes[-1]:.3f} s",
                flush=True,
            )
    return {
        "cv_mae_mean": float(np.mean(fold_maes)),
        "cv_mae_std": float(np.std(fold_maes)),
        "n_folds": float(len(fold_maes)),
    }


def tune_hyperparams(
    frame: pd.DataFrame,
    *,
    grid: list[dict[str, Any]] | None = None,
    screen_stride: int = 5,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Screen a small grid on strided LORO, then full LORO on the top configs.

    Selection uses LORO-CV only — never held-out MAE.
    Returns (best_config, all_results).
    """
    configs = grid or TUNE_GRID
    screen_rows: list[dict[str, Any]] = []
    print(
        f"Hyperparam screen: {len(configs)} configs, LORO stride={screen_stride} "
        f"({frame['race_id'].nunique()} races / {len(frame)} laps)",
        flush=True,
    )
    for i, cfg in enumerate(configs, start=1):
        params = dict(DEFAULT_XGB_PARAMS)
        params["max_depth"] = int(cfg["max_depth"])
        params["eta"] = float(cfg["eta"])
        n_rounds = int(cfg["num_boost_round"])
        print(
            f"[{i}/{len(configs)}] depth={params['max_depth']} eta={params['eta']} "
            f"rounds<={n_rounds}",
            flush=True,
        )
        metrics = loro_cv_mae(
            frame,
            params=params,
            num_boost_round=n_rounds,
            fold_stride=screen_stride,
        )
        row = {**cfg, **metrics}
        screen_rows.append(row)
        print(
            f"  -> screen CV MAE={metrics['cv_mae_mean']:.3f} "
            f"+/- {metrics['cv_mae_std']:.3f} s ({int(metrics['n_folds'])} folds)",
            flush=True,
        )

    screen_rows.sort(key=lambda r: r["cv_mae_mean"])
    # Full LORO on top 2 screened configs (or 1 if only one).
    finalists = screen_rows[: min(2, len(screen_rows))]
    print(f"\nFull LORO-CV on top {len(finalists)} screened config(s)...", flush=True)
    final_rows: list[dict[str, Any]] = []
    for i, cfg in enumerate(finalists, start=1):
        params = dict(DEFAULT_XGB_PARAMS)
        params["max_depth"] = int(cfg["max_depth"])
        params["eta"] = float(cfg["eta"])
        n_rounds = int(cfg["num_boost_round"])
        print(
            f"finalist {i}: depth={params['max_depth']} eta={params['eta']} "
            f"rounds<={n_rounds}",
            flush=True,
        )
        metrics = loro_cv_mae(
            frame,
            params=params,
            num_boost_round=n_rounds,
            fold_stride=1,
        )
        row = {
            "max_depth": cfg["max_depth"],
            "eta": cfg["eta"],
            "num_boost_round": cfg["num_boost_round"],
            **metrics,
            "screen_cv_mae_mean": cfg["cv_mae_mean"],
        }
        final_rows.append(row)
        print(
            f"  -> full CV MAE={metrics['cv_mae_mean']:.3f} "
            f"+/- {metrics['cv_mae_std']:.3f} s",
            flush=True,
        )

    final_rows.sort(key=lambda r: r["cv_mae_mean"])
    best = final_rows[0]
    best_config = {
        "max_depth": int(best["max_depth"]),
        "eta": float(best["eta"]),
        "num_boost_round": int(best["num_boost_round"]),
        "cv_mae_mean": float(best["cv_mae_mean"]),
        "cv_mae_std": float(best["cv_mae_std"]),
    }
    print(
        f"\nSelected by LORO-CV: depth={best_config['max_depth']} "
        f"eta={best_config['eta']} rounds<={best_config['num_boost_round']} "
        f"(CV MAE={best_config['cv_mae_mean']:.3f} s)",
        flush=True,
    )
    return best_config, screen_rows + final_rows


def load_training_frames(cache_dir: Path | None = None) -> pd.DataFrame:
    """Build and concatenate feature frames for all reference races."""
    import time

    import fastf1
    from fastf1.exceptions import RateLimitExceededError

    root = cache_dir or (_REPO_ROOT / "fastf1_cache")
    root.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(root))
    frames: list[pd.DataFrame] = []
    failed: list[str] = []
    n = len(REFERENCE_RACES)
    for i, (year, gp) in enumerate(REFERENCE_RACES, start=1):
        label = f"{year} {gp}"
        attempts = 0
        while True:
            attempts += 1
            try:
                frame = build_from_fastf1(year, gp)
                if frame.empty:
                    failed.append(f"{label} (empty frame)")
                    print(f"[{i}/{n}] SKIP empty {label}", flush=True)
                else:
                    frames.append(frame)
                    print(f"[{i}/{n}] OK {label}: {len(frame)} laps", flush=True)
                break
            except RateLimitExceededError:
                wait_s = 120 * attempts
                print(
                    f"[{i}/{n}] rate-limited on {label}; sleeping {wait_s}s "
                    f"(attempt {attempts})",
                    flush=True,
                )
                time.sleep(wait_s)
                if attempts >= 6:
                    failed.append(f"{label} (RateLimitExceededError)")
                    print(f"[{i}/{n}] FAIL {label}: gave up after rate limits", flush=True)
                    break
            except Exception as exc:  # noqa: BLE001 — continue corpus; log failure
                failed.append(f"{label} ({type(exc).__name__}: {exc})")
                print(f"[{i}/{n}] FAIL {label}: {exc}", flush=True)
                break
    if not frames:
        raise RuntimeError("no training frames built — is fastf1_cache populated?")
    if failed:
        print(f"WARNING: {len(failed)}/{n} reference races failed to load", flush=True)
        for item in failed:
            print(f"  - {item}", flush=True)
    return pd.concat(frames, ignore_index=True)


def train_residual_model(path: Path | None = None) -> tuple[ResidualModel, dict[str, float]]:
    """End-to-end train + save; returns model and CV metrics."""
    frame = load_training_frames()
    model = ResidualModel()
    metrics = model.fit(frame)
    model.save(path)
    return model, metrics


def train_residual_model_from_frame(
    frame: pd.DataFrame,
    *,
    path: Path | None = None,
    xgb_params: dict[str, Any] | None = None,
    num_boost_round: int | None = None,
) -> tuple[ResidualModel, dict[str, float]]:
    """LORO-CV then fit-all on an already-built frame (checkpoint path)."""
    params = dict(DEFAULT_XGB_PARAMS)
    if xgb_params:
        params.update(xgb_params)
    rounds = DEFAULT_NUM_BOOST_ROUND if num_boost_round is None else int(num_boost_round)
    model = ResidualModel(xgb_params=params, num_boost_round=rounds)
    metrics = model.fit(frame)
    model.save(path)
    return model, metrics
