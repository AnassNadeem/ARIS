"""Pooled, context-aware tyre degradation (Phase G.4).

Target: fuel-corrected, clean-lap-filtered per-lap time attributable to
degradation (E3.2 prep: fuel detrend on race, Stint/pit-out split, green-flag
filter, drop first lap of stint). Only the fitter changes: one gradient-boosted
model across the mapped C-code corpus.

Not the shipped default. Overlay is opt-in via ``ARIS_TRUE_COMPOUND_SLOPES=pooled``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from aris.eval.scoring import mae
from aris.models.cv import race_by_race_folds
from aris.models.features import estimate_fuel_kg
from aris.models.residual import (
    DEFAULT_EARLY_STOPPING_ROUNDS,
    DEFAULT_NUM_BOOST_ROUND,
    DEFAULT_XGB_PARAMS,
)
from aris.physics.compounds import compound_era, join_compound_identity
from aris.physics.deg_corrections import detrend_fuel_pace
from aris.physics.stint import detect_stints, filter_clean_laps
from aris.physics.tires import normalize_compound
from aris.physics.traffic import gaps_from_fastf1_laps
from aris.tracks import n_corners_for_event

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = _REPO_ROOT / "models" / "pooled_deg_xgb.json"
C_CODES = ("C1", "C2", "C3", "C4", "C5", "C6")
ERAS = ("2019-2021", "2022", "2023-2025", "2026")
RACE_SESSION_TYPES = frozenset({"R", "Race", "r"})

# Same toolkit as residual XGBoost; small grid, LORO only (never held-out).
TUNE_GRID: list[dict[str, Any]] = [
    {"max_depth": 3, "eta": 0.1, "num_boost_round": 80},
    {"max_depth": 4, "eta": 0.1, "num_boost_round": 80},
    {"max_depth": 4, "eta": 0.05, "num_boost_round": 120},
    {"max_depth": 6, "eta": 0.1, "num_boost_round": 80},
]

CAT_COLS = ("compound_id", "era")
NUM_COLS = (
    "tyre_life",
    "air_temp_c",
    "track_temp_c",
    "humidity_pct",
    "gap_to_nearest_s",
    "n_corners",
    "stint_position",
)
FEATURE_COLS = [*CAT_COLS, *NUM_COLS]
ENCODED_COLS = (
    [f"compound_{c}" for c in C_CODES]
    + [f"era_{e}" for e in ERAS]
    + list(NUM_COLS)
)
SLOPE_LIFE_LO = 2
SLOPE_LIFE_HI = 12


def enable_fastf1_cache(cache_dir: Path | None = None) -> Path:
    """Enable the pickle cache. HTTP sqlite cache is skipped (known serializer bug)."""
    import fastf1

    root = cache_dir or (_REPO_ROOT / "fastf1_cache")
    root.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(root), use_requests_cache=False)
    return root


def join_weather_nearest(
    laps: pd.DataFrame,
    weather: pd.DataFrame | None,
    *,
    lap_time_col: str | None = None,
) -> pd.DataFrame:
    """Nearest-timestamp join of FastF1 ``weather_data`` onto laps.

    Uses ``LapStartTime`` when present, else ``Time``. Does not interpolate or
    fill — unmatched / empty weather leaves NaN. Also returns ``weather_delta_s``
    (absolute seconds between the lap stamp and the matched weather row) so
    coverage can report join tightness rather than assuming 100%.
    """
    orig_index = laps.index
    out = laps.reset_index(drop=True).copy()
    out["air_temp_c"] = np.nan
    out["track_temp_c"] = np.nan
    out["humidity_pct"] = np.nan
    out["weather_delta_s"] = np.nan
    if weather is None or getattr(weather, "empty", True):
        out.index = orig_index
        return out
    if lap_time_col is None:
        lap_time_col = "LapStartTime" if "LapStartTime" in out.columns else "Time"
    if lap_time_col not in out.columns or "Time" not in weather.columns:
        out.index = orig_index
        return out

    left = out.reset_index(drop=False).rename(columns={"index": "_orig_idx"})
    left["_t"] = pd.to_timedelta(left[lap_time_col], errors="coerce")
    right = weather.copy()
    right["_wx_t"] = pd.to_timedelta(right["Time"], errors="coerce")
    left_ok = left.dropna(subset=["_t"]).sort_values("_t")
    keep_wx = ["_wx_t"]
    rename_wx: dict[str, str] = {}
    if "AirTemp" in right.columns:
        rename_wx["AirTemp"] = "_air"
        keep_wx.append("AirTemp")
    if "TrackTemp" in right.columns:
        rename_wx["TrackTemp"] = "_track"
        keep_wx.append("TrackTemp")
    if "Humidity" in right.columns:
        rename_wx["Humidity"] = "_hum"
        keep_wx.append("Humidity")
    right_ok = (
        right.dropna(subset=["_wx_t"]).sort_values("_wx_t")[keep_wx].rename(columns=rename_wx)
    )
    if left_ok.empty or right_ok.empty:
        out.index = orig_index
        return out

    merged = pd.merge_asof(
        left_ok,
        right_ok,
        left_on="_t",
        right_on="_wx_t",
        direction="nearest",
    )
    merged["_wdelta"] = (merged["_t"] - merged["_wx_t"]).abs().dt.total_seconds()
    idx = merged["_orig_idx"].to_numpy()
    if "_air" in merged.columns:
        out.loc[idx, "air_temp_c"] = pd.to_numeric(merged["_air"], errors="coerce").to_numpy()
    if "_track" in merged.columns:
        out.loc[idx, "track_temp_c"] = pd.to_numeric(merged["_track"], errors="coerce").to_numpy()
    if "_hum" in merged.columns:
        out.loc[idx, "humidity_pct"] = pd.to_numeric(merged["_hum"], errors="coerce").to_numpy()
    out.loc[idx, "weather_delta_s"] = pd.to_numeric(merged["_wdelta"], errors="coerce").to_numpy()
    out.index = orig_index
    return out


def _stint_deg_target(fit_pool: pd.DataFrame) -> pd.Series:
    """LapTimeS minus early-stint baseline → seconds attributable to deg + leftover confounders."""
    y = pd.Series(np.nan, index=fit_pool.index, dtype=float)
    for (_drv, _sid), grp in fit_pool.groupby(["Driver", "StintId"], sort=False):
        if grp.empty or "TyreLife" not in grp.columns:
            continue
        early = grp.nsmallest(min(2, len(grp)), "TyreLife")["LapTimeS"]
        if early.empty or not np.isfinite(early.to_numpy(dtype=float)).any():
            continue
        baseline = float(np.nanmedian(early.to_numpy(dtype=float)))
        y.loc[grp.index] = grp["LapTimeS"].to_numpy(dtype=float) - baseline
    return y


def _cast_features(frame: pd.DataFrame) -> pd.DataFrame:
    """One-hot C-code / era (unordered categoricals) plus numeric confounders.

    Native XGBoost categorical DMatrix was converting these to numpy and
    choking on 'C3'; one-hot is the same toolkit with a reliable numeric matrix.
    """
    work = frame.copy()
    cid = work["compound_id"].astype(str).str.upper()
    era = work["era"].astype(str)
    for code in C_CODES:
        work[f"compound_{code}"] = (cid == code).astype(float)
    for era_name in ERAS:
        work[f"era_{era_name}"] = (era == era_name).astype(float)
    for col in NUM_COLS:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    return work


def feature_matrix(frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    work = _cast_features(frame)
    x = work[list(ENCODED_COLS)]
    y = work["target"].to_numpy(dtype=float)
    return x, y


def _dmatrix(x: pd.DataFrame, y: np.ndarray | None = None) -> xgb.DMatrix:
    names = [str(c) for c in x.columns]
    arr = x.to_numpy(dtype=float)
    if y is None:
        return xgb.DMatrix(arr, feature_names=names)
    return xgb.DMatrix(arr, label=y, feature_names=names)


def _train_booster_df(
    x: pd.DataFrame,
    y: np.ndarray,
    *,
    params: dict[str, Any] | None = None,
    num_boost_round: int | None = None,
    early_stopping_rounds: int | None = DEFAULT_EARLY_STOPPING_ROUNDS,
    eval_fraction: float = 0.1,
) -> xgb.Booster:
    cfg = dict(DEFAULT_XGB_PARAMS)
    if params:
        cfg.update({k: v for k, v in params.items() if k != "num_boost_round"})
    cfg.pop("enable_categorical", None)
    rounds = DEFAULT_NUM_BOOST_ROUND if num_boost_round is None else int(num_boost_round)
    n = len(y)
    use_es = (
        early_stopping_rounds is not None
        and early_stopping_rounds > 0
        and 0.0 < eval_fraction < 0.5
        and n >= 50
    )
    if use_es:
        cut = max(1, int(n * (1.0 - eval_fraction)))
        dtrain = _dmatrix(x.iloc[:cut], y[:cut])
        deval = _dmatrix(x.iloc[cut:], y[cut:])
        return xgb.train(
            cfg,
            dtrain,
            num_boost_round=rounds,
            evals=[(deval, "eval")],
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=False,
        )
    dtrain = _dmatrix(x, y)
    return xgb.train(cfg, dtrain, num_boost_round=rounds, verbose_eval=False)


class PooledDegModel:
    """XGBoost regressor: degradation-attributable lap time (s) given context + C-code."""

    def __init__(
        self,
        booster: xgb.Booster | None = None,
        *,
        xgb_params: dict[str, Any] | None = None,
        num_boost_round: int | None = None,
        context_medians: dict[str, float] | None = None,
    ) -> None:
        self._booster = booster
        self._xgb_params = dict(xgb_params or DEFAULT_XGB_PARAMS)
        self._num_boost_round = (
            DEFAULT_NUM_BOOST_ROUND if num_boost_round is None else int(num_boost_round)
        )
        self.context_medians = dict(context_medians or {})

    @property
    def is_fitted(self) -> bool:
        return self._booster is not None

    def fit(self, frame: pd.DataFrame, *, loro: bool = True) -> dict[str, float]:
        if frame.empty:
            raise ValueError("cannot fit on empty frame")
        fold_maes: list[float] = []
        if loro:
            n_events = frame["event_id"].nunique()
            print(f"LORO-CV over {n_events} events / {len(frame)} laps...", flush=True)
            for i, (train_idx, test_idx) in enumerate(
                race_by_race_folds(frame, race_col="event_id"), start=1
            ):
                train = frame.iloc[train_idx]
                test = frame.iloc[test_idx]
                x_train, y_train = feature_matrix(train)
                x_test, y_test = feature_matrix(test)
                booster = _train_booster_df(
                    x_train,
                    y_train,
                    params=self._xgb_params,
                    num_boost_round=self._num_boost_round,
                )
                preds = booster.predict(_dmatrix(x_test))
                fold_mae = mae(y_test, preds)
                fold_maes.append(fold_mae)
                if i == 1 or i % 10 == 0 or i == n_events:
                    print(f"  fold {i}/{n_events}: MAE={fold_mae:.3f} s", flush=True)
        x_all, y_all = feature_matrix(frame)
        self._booster = _train_booster_df(
            x_all,
            y_all,
            params=self._xgb_params,
            num_boost_round=self._num_boost_round,
        )
        self.context_medians = _context_medians(frame)
        out: dict[str, float] = {}
        if fold_maes:
            out["cv_mae_mean"] = float(np.mean(fold_maes))
            out["cv_mae_std"] = float(np.std(fold_maes))
            out["n_folds"] = float(len(fold_maes))
        return out

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("model not fitted")
        x, _ = feature_matrix(features.assign(target=features.get("target", 0.0)))
        return self._booster.predict(_dmatrix(x))  # type: ignore[union-attr]

    def feature_importances(self, importance_type: str = "gain") -> dict[str, float]:
        if not self.is_fitted:
            raise RuntimeError("model not fitted")
        raw = self._booster.get_score(importance_type=importance_type)  # type: ignore[union-attr]
        cols = list(ENCODED_COLS)
        named: dict[str, float] = {}
        for key, val in raw.items():
            if key in cols:
                named[key] = float(val)
            elif key.startswith("f") and key[1:].isdigit():
                idx = int(key[1:])
                if 0 <= idx < len(cols):
                    named[cols[idx]] = float(val)
            else:
                named[str(key)] = float(val)
        total = sum(named.values()) or 1.0
        norm = {k: v / total for k, v in named.items()}
        # Grouped views (already on the same 1.0 scale as the one-hot shares).
        norm["compound_id"] = sum(v for k, v in norm.items() if k.startswith("compound_"))
        norm["era"] = sum(v for k, v in norm.items() if k.startswith("era_"))
        return dict(sorted(norm.items(), key=lambda kv: -kv[1]))

    def predict_one(self, row: dict[str, Any]) -> float:
        frame = pd.DataFrame([{**row, "target": 0.0}])
        return float(self.predict(frame)[0])

    def slope_at_context(
        self,
        compound_id: str,
        era: str,
        context: dict[str, float] | None = None,
        *,
        life_lo: int = SLOPE_LIFE_LO,
        life_hi: int = SLOPE_LIFE_HI,
    ) -> float:
        """Finite-difference s/lap holding every covariate except tyre_life fixed."""
        ctx = {**self.context_medians, **(context or {})}
        lo = {
            "compound_id": compound_id,
            "era": era,
            "tyre_life": life_lo,
            **{k: ctx.get(k) for k in NUM_COLS if k != "tyre_life"},
        }
        hi = dict(lo)
        hi["tyre_life"] = life_hi
        return (self.predict_one(hi) - self.predict_one(lo)) / float(life_hi - life_lo)

    def save(self, path: Path | None = None) -> Path:
        if not self.is_fitted:
            raise RuntimeError("model not fitted")
        dest = path or DEFAULT_MODEL_PATH
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(dest))  # type: ignore[union-attr]
        meta = {
            "feature_cols": list(FEATURE_COLS),
            "encoded_cols": list(ENCODED_COLS),
            "version": 2,
            "xgb_params": self._xgb_params,
            "num_boost_round": self._num_boost_round,
            "context_medians": self.context_medians,
        }
        dest.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return dest

    @classmethod
    def load(cls, path: Path | None = None) -> PooledDegModel:
        src = path or DEFAULT_MODEL_PATH
        if not src.exists():
            raise FileNotFoundError(f"no pooled deg model at {src}")
        booster = xgb.Booster()
        booster.load_model(str(src))
        meta_path = src.with_suffix(".meta.json")
        params = dict(DEFAULT_XGB_PARAMS)
        n_rounds = DEFAULT_NUM_BOOST_ROUND
        medians: dict[str, float] = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta.get("xgb_params"), dict):
                params.update(meta["xgb_params"])
            if meta.get("num_boost_round") is not None:
                n_rounds = int(meta["num_boost_round"])
            if isinstance(meta.get("context_medians"), dict):
                medians = {str(k): float(v) for k, v in meta["context_medians"].items() if v is not None}
        return cls(booster, xgb_params=params, num_boost_round=n_rounds, context_medians=medians)


def _context_medians(frame: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for col in NUM_COLS:
        if col not in frame.columns:
            continue
        vals = pd.to_numeric(frame[col], errors="coerce")
        if vals.notna().any():
            out[col] = float(vals.median())
    return out


def loro_cv_mae(
    frame: pd.DataFrame,
    *,
    params: dict[str, Any],
    num_boost_round: int,
    fold_stride: int = 1,
    quiet: bool = False,
) -> dict[str, float]:
    fold_maes: list[float] = []
    folds = list(race_by_race_folds(frame, race_col="event_id"))
    selected = list(enumerate(folds, start=1))
    if fold_stride > 1:
        selected = selected[::fold_stride]
    n_eval = len(selected)
    for j, (i, (train_idx, test_idx)) in enumerate(selected, start=1):
        train = frame.iloc[train_idx]
        test = frame.iloc[test_idx]
        x_train, y_train = feature_matrix(train)
        x_test, y_test = feature_matrix(test)
        booster = _train_booster_df(
            x_train, y_train, params=params, num_boost_round=num_boost_round
        )
        preds = booster.predict(_dmatrix(x_test))
        fold_maes.append(mae(y_test, preds))
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
    screen_stride: int = 3,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Screen on strided LORO, full LORO on top 2. Never uses held-out MAE."""
    configs = grid or TUNE_GRID
    screen_rows: list[dict[str, Any]] = []
    print(
        f"Pooled-deg hyperparam screen: {len(configs)} configs, LORO stride={screen_stride} "
        f"({frame['event_id'].nunique()} events / {len(frame)} laps)",
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
            frame, params=params, num_boost_round=n_rounds, fold_stride=screen_stride
        )
        row = {**cfg, **metrics}
        screen_rows.append(row)
        print(
            f"  -> screen CV MAE={metrics['cv_mae_mean']:.3f} "
            f"+/- {metrics['cv_mae_std']:.3f} s ({int(metrics['n_folds'])} folds)",
            flush=True,
        )
    screen_rows.sort(key=lambda r: r["cv_mae_mean"])
    finalists = screen_rows[: min(2, len(screen_rows))]
    print(f"\nFull LORO-CV on top {len(finalists)} screened config(s)...", flush=True)
    final_rows: list[dict[str, Any]] = []
    for i, cfg in enumerate(finalists, start=1):
        params = dict(DEFAULT_XGB_PARAMS)
        params["max_depth"] = int(cfg["max_depth"])
        params["eta"] = float(cfg["eta"])
        n_rounds = int(cfg["num_boost_round"])
        metrics = loro_cv_mae(frame, params=params, num_boost_round=n_rounds, fold_stride=1)
        row = {
            "max_depth": cfg["max_depth"],
            "eta": cfg["eta"],
            "num_boost_round": cfg["num_boost_round"],
            **metrics,
            "screen_cv_mae_mean": cfg["cv_mae_mean"],
        }
        final_rows.append(row)
        print(
            f"  -> full CV MAE={metrics['cv_mae_mean']:.3f} +/- {metrics['cv_mae_std']:.3f} s",
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


def monotonicity_at_context(
    model: PooledDegModel,
    era: str,
    context: dict[str, float] | None = None,
    codes: tuple[str, ...] = C_CODES,
) -> dict[str, Any]:
    slopes = {c: model.slope_at_context(c, era, context) for c in codes}
    present = [(c, slopes[c]) for c in codes if np.isfinite(slopes[c])]
    ok = True
    reason = "ok"
    for (a, va), (b, vb) in zip(present, present[1:], strict=False):
        if not (vb > va):
            ok = False
            reason = f"ordering failed {a}={va:.4f} not < {b}={vb:.4f}"
            break
    if ok and present:
        reason = "ok " + " < ".join(f"{c}={v:.4f}" for c, v in present)
    return {"era": era, "slopes": {c: round(float(v), 4) for c, v in slopes.items()}, "monotonic_ok": ok, "reason": reason}


def build_session_frame(
    session,
    *,
    year: int,
    event: str,
    session_type: str,
    round_no: int | None = None,
) -> pd.DataFrame:
    """E3.2 prep → per-lap G4 feature frame. Empty if nothing joinable / no C-codes."""
    try:
        enriched = detect_stints(session.laps).reset_index(drop=True)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    if "LapTimeS" not in enriched.columns:
        return pd.DataFrame()

    fuel_corrected = False
    stype = str(session_type).upper()
    if stype in RACE_SESSION_TYPES or stype in {"R"}:
        total_laps = int(getattr(session, "total_laps", None) or 57)
        enriched = detrend_fuel_pace(enriched, total_laps=total_laps)
        fuel_corrected = True

    first_lap = enriched.groupby(["Driver", "StintId"])["LapNumber"].transform("min")
    clean = filter_clean_laps(enriched)
    fit_pool = clean.loc[clean["LapNumber"] != first_lap.loc[clean.index]].copy()
    fit_pool = fit_pool.reset_index(drop=True)
    if fit_pool.empty:
        return pd.DataFrame()

    weather = getattr(session, "weather_data", None)
    fit_pool = join_weather_nearest(fit_pool, weather)
    gaps = gaps_from_fastf1_laps(enriched)
    if not gaps.empty:
        g = gaps.rename(columns={"LapNumber": "_gap_lap", "Driver": "_gap_drv"})
        g["_gap_lap"] = pd.to_numeric(g["_gap_lap"], errors="coerce").astype("Int64")
        fit_pool["_lap_i"] = pd.to_numeric(fit_pool["LapNumber"], errors="coerce").astype("Int64")
        fit_pool = fit_pool.merge(
            g[["_gap_drv", "_gap_lap", "min_nearby_s"]],
            left_on=["Driver", "_lap_i"],
            right_on=["_gap_drv", "_gap_lap"],
            how="left",
        )
        fit_pool["gap_to_nearest_s"] = pd.to_numeric(fit_pool["min_nearby_s"], errors="coerce")
        fit_pool = fit_pool.drop(
            columns=["_gap_drv", "_gap_lap", "min_nearby_s", "_lap_i"], errors="ignore"
        )
    else:
        fit_pool["gap_to_nearest_s"] = np.nan

    n_corners = n_corners_for_event(event)
    fit_pool["n_corners"] = n_corners if n_corners is not None else np.nan
    fit_pool["stint_position"] = pd.to_numeric(fit_pool["StintId"], errors="coerce")
    fit_pool["tyre_life"] = pd.to_numeric(fit_pool["TyreLife"], errors="coerce")
    total_laps = int(getattr(session, "total_laps", None) or 57)
    fit_pool["fuel_kg"] = fit_pool["LapNumber"].map(
        lambda n: estimate_fuel_kg(int(n), total_laps=total_laps)
    )
    fit_pool["target"] = _stint_deg_target(fit_pool)
    fit_pool = join_compound_identity(
        fit_pool, year=year, event=event, round_no=round_no
    )
    fit_pool["compound_id"] = fit_pool["CompoundIdentity"].map(
        lambda c: str(c).upper() if str(c).upper() in C_CODES else None
    )
    fit_pool["era"] = compound_era(year)
    fit_pool["year"] = year
    fit_pool["event"] = event
    fit_pool["session_type"] = session_type
    fit_pool["event_id"] = f"{year}-{event}"
    fit_pool["race_id"] = f"{year}-{event}-{session_type}"
    fit_pool["FuelCorrected"] = fuel_corrected
    fit_pool["compound"] = fit_pool["Compound"].map(normalize_compound)

    keep = list(
        dict.fromkeys(
            [
                "event_id",
                "race_id",
                "year",
                "event",
                "session_type",
                "Driver",
                "LapNumber",
                "StintId",
                "compound",
                "compound_id",
                "era",
                "target",
                "fuel_kg",
                "FuelCorrected",
                "weather_delta_s",
                *FEATURE_COLS,
            ]
        )
    )
    out = fit_pool[keep].copy()
    out = out.loc[out["compound_id"].isin(C_CODES)]
    out = out.loc[out["target"].notna() & np.isfinite(out["target"].to_numpy(dtype=float))]
    return out.reset_index(drop=True)


def coverage_row(frame: pd.DataFrame, col: str) -> dict[str, Any]:
    if frame.empty or col not in frame.columns:
        return {"n": 0, "n_present": 0, "frac": None}
    s = frame[col]
    n = int(len(s))
    n_present = int(s.notna().sum())
    return {
        "n": n,
        "n_present": n_present,
        "frac": (n_present / n) if n else None,
    }
