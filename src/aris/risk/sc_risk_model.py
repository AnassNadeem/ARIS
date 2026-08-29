"""SC/VSC risk — logistic models for P(neutralisation in the next 5 / 10 laps).

Trained on 2024, tested on 2025. Missing model files return the historical
base rates (0.07 / 0.12) rather than crashing.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

_log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_5_PATH = _REPO_ROOT / "models" / "sc_risk_5laps.pkl"
MODEL_10_PATH = _REPO_ROOT / "models" / "sc_risk_10laps.pkl"
RATES_PATH = _REPO_ROOT / "data" / "sc_historical_rates.json"
DATASET_PATH = _REPO_ROOT / "data" / "sc_risk_dataset.parquet"

BASE_RATE_5 = 0.07
BASE_RATE_10 = 0.12

NUMERIC_FEATURES = [
    "lap_number",
    "race_frac",
    "rain_flag",
    "track_temp_c",
    "retirements_last_5_laps",
    "yellow_flags_last_3_laps",
    "field_density",
    "historical_sc_rate",
]
CAT_FEATURES = ["circuit_id"]
FEATURE_COLS = CAT_FEATURES + NUMERIC_FEATURES

_MODELS: dict[str, Any] | None = None
_RATES: dict[str, float] | None = None


def circuit_key(name: str) -> str:
    from aris.physics.tires import _normalize_circuit_key

    token = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(name or ""))
        if not unicodedata.combining(ch)
    )
    key = _normalize_circuit_key(token)
    extra = {
        "yas_island": "abu_dhabi",
        "yasisland": "abu_dhabi",
        "marina_bay": "singapore",
        "marinabay": "singapore",
        "budapest": "hungary",
        "spa_francorchamps": "belgium",
        "spafrancorchamps": "belgium",
        "le_castellet": "france",
        "lecastellet": "france",
        "montreal": "canada",
        "catalunya": "spain",
    }
    return extra.get(key, extra.get(key.replace("_", ""), key))


def is_sc_vsc_deployment(message: str) -> bool:
    """True for SC/VSC *deployment* radio, not endings or infringement notes."""
    text = str(message or "").upper()
    if "INFRINGEMENT" in text or "ENDING" in text or "LAPPED CAR" in text:
        return False
    if "SAFETY CAR" not in text and "VIRTUAL SAFETY CAR" not in text:
        return False
    return "DEPLOYED" in text


def sc_event_laps(rcm: pd.DataFrame | None) -> set[int]:
    """Lap numbers where an SC or VSC was deployed."""
    if rcm is None or getattr(rcm, "empty", True):
        return set()
    if "Message" not in rcm.columns:
        return set()
    hit = rcm[rcm["Message"].map(is_sc_vsc_deployment)]
    if hit.empty or "Lap" not in hit.columns:
        return set()
    out: set[int] = set()
    for raw in hit["Lap"]:
        if pd.isna(raw):
            continue
        try:
            lap = int(raw)
        except (TypeError, ValueError):
            continue
        if lap > 0:
            out.add(lap)
    return out


def load_historical_rates(path: Path | None = None) -> dict[str, float]:
    global _RATES
    if _RATES is not None and path is None:
        return _RATES
    src = path or RATES_PATH
    if not src.is_file():
        return {}
    data = json.loads(src.read_text(encoding="utf-8"))
    rates = {circuit_key(k): float(v) for k, v in data.items() if k != "_mean"}
    if path is None:
        _RATES = rates
    return rates


def historical_sc_rate_for(circuit: str, rates: dict[str, float] | None = None) -> float:
    table = rates if rates is not None else load_historical_rates()
    key = circuit_key(circuit)
    if key in table:
        return float(table[key])
    if table:
        return float(sum(table.values()) / len(table))
    return 0.50


def _td_seconds(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def field_density_from_times(times: list[float], window_s: float = 2.0) -> float:
    """Fraction of cars that have another car within ``window_s``."""
    if len(times) < 2:
        return 0.0
    arr = np.sort(np.asarray(times, dtype=float))
    close = 0
    for i, t in enumerate(arr):
        left = i > 0 and (t - arr[i - 1]) <= window_s
        right = i + 1 < len(arr) and (arr[i + 1] - t) <= window_s
        if left or right:
            close += 1
    return float(close / len(arr))


def extras_from_fastf1(
    laps: pd.DataFrame,
    lap_number: int,
    *,
    rcm: pd.DataFrame | None = None,
    results: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Cross-car extras from a FastF1 laps frame (A0 columns)."""
    return {
        "retirements_last_5_laps": float(
            _retirements_fastf1(laps, lap_number, results)
        ),
        "yellow_flags_last_3_laps": float(_yellows_fastf1(laps, rcm, lap_number)),
        "field_density": float(_density_fastf1(laps, lap_number)),
    }


def extras_from_db_laps(laps: pd.DataFrame, lap_number: int) -> dict[str, float]:
    """Cross-car extras from ``db.fetch_all_laps()`` (all 20 cars)."""
    if laps is None or laps.empty:
        return {
            "retirements_last_5_laps": 0.0,
            "yellow_flags_last_3_laps": 0.0,
            "field_density": 0.0,
        }
    return {
        "retirements_last_5_laps": float(_retirements_db(laps, lap_number)),
        "yellow_flags_last_3_laps": float(_yellows_db(laps, lap_number)),
        "field_density": float(_density_db(laps, lap_number)),
    }


def _retirements_fastf1(
    laps: pd.DataFrame, lap_number: int, results: pd.DataFrame | None
) -> int:
    if laps.empty or "Driver" not in laps.columns or "LapNumber" not in laps.columns:
        return 0
    last = laps.groupby("Driver")["LapNumber"].max()
    disappeared = (last >= lap_number - 4) & (last < lap_number)
    return int(disappeared.sum())


def _retirements_db(laps: pd.DataFrame, lap_number: int) -> int:
    if "code" not in laps.columns or "lap_number" not in laps.columns:
        return 0
    last = laps.groupby("code")["lap_number"].max()
    disappeared = (last >= lap_number - 4) & (last < lap_number)
    return int(disappeared.sum())


def _yellows_fastf1(
    laps: pd.DataFrame, rcm: pd.DataFrame | None, lap_number: int
) -> int:
    lo, hi = lap_number - 2, lap_number
    if rcm is not None and not rcm.empty and "Flag" in rcm.columns and "Lap" in rcm.columns:
        flags = rcm["Flag"].astype(str).str.upper().str.contains("YELLOW", na=False)
        in_win = (rcm["Lap"] >= lo) & (rcm["Lap"] <= hi)
        n = int((flags & in_win).sum())
        if n:
            return n
    if "TrackStatus" in laps.columns and "LapNumber" in laps.columns:
        window = laps[(laps["LapNumber"] >= lo) & (laps["LapNumber"] <= hi)]
        n_laps = 0
        for _, grp in window.groupby("LapNumber"):
            if grp["TrackStatus"].astype(str).str.contains("2", na=False).any():
                n_laps += 1
        return n_laps
    return 0


def _yellows_db(laps: pd.DataFrame, lap_number: int) -> int:
    if "track_status" not in laps.columns or "lap_number" not in laps.columns:
        return 0
    window = laps[
        (laps["lap_number"] >= lap_number - 2) & (laps["lap_number"] <= lap_number)
    ]
    n_laps = 0
    for _, grp in window.groupby("lap_number"):
        if grp["track_status"].astype(str).str.contains("2", na=False).any():
            n_laps += 1
    return n_laps


def _density_fastf1(laps: pd.DataFrame, lap_number: int) -> float:
    if laps.empty or "LapNumber" not in laps.columns:
        return 0.0
    row = laps[laps["LapNumber"] == lap_number]
    times: list[float] = []
    if "Time" in row.columns:
        for value in row["Time"]:
            sec = _td_seconds(value)
            if sec is not None:
                times.append(sec)
    return field_density_from_times(times)


def _density_db(laps: pd.DataFrame, lap_number: int) -> float:
    if "code" not in laps.columns or "lap_number" not in laps.columns:
        return 0.0
    if "lap_time_s" not in laps.columns:
        return 0.0
    on_lap = laps[laps["lap_number"] == lap_number]
    if on_lap.empty:
        return 0.0
    prior = laps[laps["lap_number"] <= lap_number]
    cum = prior.groupby("code")["lap_time_s"].sum()
    times: list[float] = []
    for code in on_lap["code"].unique():
        if code in cum.index and pd.notna(cum[code]):
            times.append(float(cum[code]))
    return field_density_from_times(times)


def weather_at_lap(
    weather: pd.DataFrame | None, lap_time: Any
) -> tuple[bool, float | None]:
    """Nearest FastF1 weather sample → (rain_flag, track_temp_c)."""
    if weather is None or weather.empty:
        return False, None
    target = _td_seconds(lap_time)
    if target is None or "Time" not in weather.columns:
        rain = bool(weather["Rainfall"].iloc[0]) if "Rainfall" in weather.columns else False
        temp = (
            float(weather["TrackTemp"].iloc[0])
            if "TrackTemp" in weather.columns and pd.notna(weather["TrackTemp"].iloc[0])
            else None
        )
        return rain, temp
    secs = weather["Time"].map(_td_seconds)
    valid = secs.dropna()
    if valid.empty:
        return False, None
    idx = (valid - target).abs().idxmin()
    row = weather.loc[idx]
    rain = bool(row["Rainfall"]) if "Rainfall" in weather.columns else False
    temp = (
        float(row["TrackTemp"])
        if "TrackTemp" in weather.columns and pd.notna(row.get("TrackTemp"))
        else None
    )
    return rain, temp


def label_windows(lap_number: int, sc_laps: set[int]) -> tuple[int, int]:
    next_5 = {lap_number + i for i in range(1, 6)}
    next_10 = {lap_number + i for i in range(1, 11)}
    return int(bool(sc_laps & next_5)), int(bool(sc_laps & next_10))


def default_feature_row(
    *,
    circuit: str,
    lap_number: int,
    total_laps: int,
    rain_flag: bool = False,
    track_temp_c: float | None = None,
    extras: dict[str, float] | None = None,
    rates: dict[str, float] | None = None,
) -> dict[str, Any]:
    extra = extras or {}
    total = max(int(total_laps), 1)
    return {
        "circuit_id": circuit_key(circuit),
        "lap_number": int(lap_number),
        "race_frac": float(lap_number) / total,
        "rain_flag": 1.0 if rain_flag else 0.0,
        "track_temp_c": float(track_temp_c) if track_temp_c is not None else 30.0,
        "retirements_last_5_laps": float(extra.get("retirements_last_5_laps", 0.0)),
        "yellow_flags_last_3_laps": float(extra.get("yellow_flags_last_3_laps", 0.0)),
        "field_density": float(extra.get("field_density", 0.0)),
        "historical_sc_rate": historical_sc_rate_for(circuit, rates),
    }


def features_from_state(state: Any, extras: dict[str, float] | None = None) -> dict[str, Any]:
    circuit = str(getattr(state, "country", None) or getattr(state, "track_name", "") or "")
    rain = bool(getattr(state, "rainfall", False))
    return default_feature_row(
        circuit=circuit,
        lap_number=int(state.lap_number),
        total_laps=int(getattr(state, "total_laps", 0) or 1),
        rain_flag=rain,
        track_temp_c=getattr(state, "track_temp_c", None),
        extras=extras,
    )


def _make_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CAT_FEATURES,
            ),
            ("num", "passthrough", NUMERIC_FEATURES),
        ]
    )
    clf = LogisticRegression(
        class_weight="balanced",
        max_iter=2000,
        solver="lbfgs",
        random_state=0,
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def load_sc_risk_models(
    path_5: Path | None = None,
    path_10: Path | None = None,
) -> dict[str, Pipeline] | None:
    """Load both fitted pipelines, or None if either file is missing."""
    global _MODELS
    p5 = path_5 or MODEL_5_PATH
    p10 = path_10 or MODEL_10_PATH
    if _MODELS is not None and path_5 is None and path_10 is None:
        return _MODELS
    if not p5.is_file() or not p10.is_file():
        return None
    models = {
        "5": joblib.load(p5),
        "10": joblib.load(p10),
    }
    if path_5 is None and path_10 is None:
        _MODELS = models
    return models


def reset_sc_risk_cache() -> None:
    global _MODELS, _RATES
    _MODELS = None
    _RATES = None


def predict_sc_risk(
    features: dict[str, Any] | None = None,
    *,
    state: Any = None,
    extras: dict[str, float] | None = None,
    models: dict[str, Pipeline] | None = None,
) -> tuple[float, float]:
    """Return ``(p_sc_next_5, p_sc_next_10)`` in ``[0, 1]`` with p5 ≤ p10."""
    fitted = models if models is not None else load_sc_risk_models()
    if fitted is None:
        return BASE_RATE_5, BASE_RATE_10
    row = features if features is not None else features_from_state(state, extras)
    frame = pd.DataFrame([row], columns=FEATURE_COLS)
    p5 = float(fitted["5"].predict_proba(frame)[0, 1])
    p10 = float(fitted["10"].predict_proba(frame)[0, 1])
    p5 = min(max(p5, 0.0), 1.0)
    p10 = min(max(p10, 0.0), 1.0)
    if p5 > p10:
        p5 = p10
    return p5, p10


def attach_sc_risk(
    state: Any,
    *,
    extras: dict[str, float] | None = None,
    all_laps: pd.DataFrame | None = None,
) -> Any:
    """Populate ``p_sc_next_5_laps`` / ``p_sc_next_10_laps`` on a RaceState copy."""
    extra = extras
    if extra is None and all_laps is not None:
        extra = extras_from_db_laps(all_laps, int(state.lap_number))
    try:
        p5, p10 = predict_sc_risk(state=state, extras=extra)
    except Exception:
        _log.exception("SC risk predict failed — using base rates")
        p5, p10 = BASE_RATE_5, BASE_RATE_10
    return state.model_copy(
        update={"p_sc_next_5_laps": p5, "p_sc_next_10_laps": p10}
    )


def _precision_eq_recall_threshold(y: np.ndarray, p: np.ndarray) -> float | None:
    if y.max() == y.min():
        return None
    prec, rec, thr = precision_recall_curve(y, p)
    if len(thr) == 0:
        return None
    diffs = np.abs(prec[:-1] - rec[:-1])
    return float(thr[int(np.argmin(diffs))])


def evaluate_split(
    model: Pipeline, frame: pd.DataFrame, y: np.ndarray
) -> dict[str, float | None]:
    p = model.predict_proba(frame[FEATURE_COLS])[:, 1]
    auc = float(roc_auc_score(y, p)) if y.max() != y.min() else None
    brier = float(brier_score_loss(y, p))
    pos = p[y == 1]
    neg = p[y == 0]
    return {
        "auc_roc": auc,
        "brier": brier,
        "mean_p_on_sc": float(pos.mean()) if len(pos) else None,
        "mean_p_on_non_sc": float(neg.mean()) if len(neg) else None,
        "threshold_prec_eq_rec": _precision_eq_recall_threshold(y, p),
        "n": int(len(y)),
        "n_pos": int(y.sum()),
        "pos_rate": float(y.mean()),
    }


def train_and_evaluate(
    df: pd.DataFrame,
    *,
    path_5: Path | None = None,
    path_10: Path | None = None,
) -> dict[str, Any]:
    """Train on 2024, test on 2025. Writes the two joblib files."""
    need = FEATURE_COLS + ["year", "sc_in_next_5", "sc_in_next_10"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"dataset missing columns: {missing}")

    train = df[df["year"] == 2024].copy()
    test = df[df["year"] == 2025].copy()
    if train.empty or test.empty:
        raise ValueError("need both 2024 (train) and 2025 (test) rows")

    metrics: dict[str, Any] = {
        "train_n": int(len(train)),
        "test_n": int(len(test)),
        "train_pos_rate_5": float(train["sc_in_next_5"].mean()),
        "train_pos_rate_10": float(train["sc_in_next_10"].mean()),
        "test_pos_rate_5": float(test["sc_in_next_5"].mean()),
        "test_pos_rate_10": float(test["sc_in_next_10"].mean()),
    }
    out_5 = path_5 or MODEL_5_PATH
    out_10 = path_10 or MODEL_10_PATH
    out_5.parent.mkdir(parents=True, exist_ok=True)

    for horizon, label, dest in (
        (5, "sc_in_next_5", out_5),
        (10, "sc_in_next_10", out_10),
    ):
        pipe = _make_pipeline()
        pipe.fit(train[FEATURE_COLS], train[label].astype(int))
        joblib.dump(pipe, dest)
        metrics[f"sc_in_next_{horizon}"] = evaluate_split(
            pipe, test, test[label].astype(int).to_numpy()
        )
        metrics[f"sc_in_next_{horizon}"]["model_path"] = str(dest)

    reset_sc_risk_cache()
    return metrics


def main() -> int:
    if not DATASET_PATH.is_file():
        print(f"dataset missing: {DATASET_PATH}")
        print("run: python scripts/build_sc_risk_dataset.py")
        return 1
    df = pd.read_parquet(DATASET_PATH)
    metrics = train_and_evaluate(df)
    print(json.dumps(metrics, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
