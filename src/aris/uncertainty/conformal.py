"""Split conformal prediction for remaining-race delta bands."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[3]
CONFORMAL_PATH = _REPO_ROOT / "data" / "conformal_result.json"

_CACHE: dict[str, Any] | None = None


def fit_conformal(residuals: np.ndarray, alpha: float = 0.10) -> dict:
    """
    Given residuals (actual - predicted) from a calibration set,
    return conformal quantile q_hat for (1-alpha) coverage.

    Uses split conformal prediction (Venn-Abers variant is not needed here —
    simple split conformal is sufficient and easier to explain).
    """
    arr = np.asarray(residuals, dtype=float)
    arr = arr[np.isfinite(arr)]
    abs_errors = np.abs(arr)
    n = len(abs_errors)
    if n == 0:
        return {
            "q_hat": 0.0,
            "alpha": alpha,
            "n_calibration": 0,
            "median_abs_error": 0.0,
            "p90_abs_error": 0.0,
        }
    # Conformal quantile: ceil((n+1)(1-alpha))/n quantile of |errors|
    level = math.ceil((n + 1) * (1 - alpha)) / n
    q_hat = float(np.quantile(abs_errors, min(level, 1.0)))
    return {
        "q_hat": q_hat,
        "alpha": alpha,
        "n_calibration": n,
        "median_abs_error": float(np.median(abs_errors)),
        "p90_abs_error": float(np.quantile(abs_errors, 0.90)),
    }


def prediction_interval(
    point_estimate: float,
    conformal_result: dict,
) -> tuple[float, float]:
    q = float(conformal_result["q_hat"])
    return float(point_estimate) - q, float(point_estimate) + q


def empirical_coverage(
    residuals: np.ndarray, q_hat: float
) -> float | None:
    arr = np.asarray(residuals, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return None
    return float(np.mean(np.abs(arr) <= q_hat))


def load_conformal_result(path: Path | None = None) -> dict | None:
    global _CACHE
    src = path or CONFORMAL_PATH
    if _CACHE is not None and path is None:
        return _CACHE
    if not src.is_file():
        return None
    data = json.loads(src.read_text(encoding="utf-8"))
    if path is None:
        _CACHE = data
    return data


def reset_conformal_cache() -> None:
    global _CACHE
    _CACHE = None


def conformal_for_stint(
    result: dict | None, laps_remaining: int
) -> dict | None:
    """Pick short / long / all-dry payload for the current remainder."""
    if not result:
        return None
    if laps_remaining < 20 and isinstance(result.get("short"), dict):
        if result["short"].get("n_calibration", 0):
            return result["short"]
    if laps_remaining >= 20 and isinstance(result.get("long"), dict):
        if result["long"].get("n_calibration", 0):
            return result["long"]
    if result.get("q_hat") is not None:
        return result
    return None


def save_conformal_result(payload: dict, path: Path | None = None) -> Path:
    dest = path or CONFORMAL_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    reset_conformal_cache()
    return dest
