"""T9 FP2 long-run degradation calibration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from aris.physics.fp2_calibration import (
    calibrate_race_weekend,
    clear_calibration_cache,
    fit_fp2_slope,
)
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, get_deg_slope

_CACHE = Path(__file__).resolve().parents[1] / "fastf1_cache"


def _fastf1_cache_ok() -> bool:
    return _CACHE.is_dir() and any(_CACHE.iterdir())


@pytest.fixture(autouse=True)
def _clear_fp2_cache():
    clear_calibration_cache()
    yield
    clear_calibration_cache()


def test_slope_validity_gate():
    """Slopes with r² < 0.1 or n_obs < 15 should set valid=False."""
    small_df = pd.DataFrame(
        {
            "tyre_life": [1, 2, 3],
            "lap_time_s": [92.1, 92.15, 92.2],
            "compound": ["HARD"] * 3,
            "stint_id": [0] * 3,
        }
    )
    result = fit_fp2_slope(small_df, "HARD")
    assert result["valid"] is False


def test_fit_rejects_negative_stint_slope():
    df = pd.DataFrame(
        {
            "tyre_life": list(range(1, 16)) + list(range(1, 16)),
            "lap_time_s": [90.0 - 0.05 * i for i in range(15)]
            + [91.0 - 0.04 * i for i in range(15)],
            "compound": ["HARD"] * 30,
            "stint_id": [0] * 15 + [1] * 15,
        }
    )
    result = fit_fp2_slope(df, "HARD")
    assert result["valid"] is False


def test_fit_accepts_two_positive_stints():
    df = pd.DataFrame(
        {
            "tyre_life": list(range(1, 16)) + list(range(1, 16)),
            "lap_time_s": [90.0 + 0.06 * i for i in range(15)]
            + [91.0 + 0.05 * i for i in range(15)],
            "compound": ["HARD"] * 30,
            "stint_id": [0] * 15 + [1] * 15,
        }
    )
    result = fit_fp2_slope(df, "HARD")
    assert result["valid"] is True
    assert result["slope"] > 0.03
    assert result["n_obs"] >= 15


def test_fallback_when_insufficient_fp2_data(monkeypatch):
    """When practice cannot be loaded, fall back to a plausible HARD slope."""
    monkeypatch.setattr(
        "aris.physics.fp2_calibration._load_practice_session",
        lambda *a, **k: None,
    )
    cal = calibrate_race_weekend(2024, 6)
    assert 0.02 <= cal["HARD"] <= 0.08
    assert cal["_source"]["HARD"] in {"g15", "circuit_prior"}
    assert cal["_valid"] is True


@pytest.mark.skipif(not _fastf1_cache_ok(), reason="FastF1 cache not available")
def test_bahrain_2024_hard_slope_steeper_than_g15():
    """Bahrain 2024 is round 1. FP2 has no HARD long runs (SOFT race-sims only).

    HARD must still come out steeper than G1.5 0.03 via fp2 / fp2_scaled
    transfer from those SOFT long runs — that is the Cause-A mechanism.
    """
    cal = calibrate_race_weekend(2024, 1)
    assert cal["HARD"] > 0.03, f"Expected Bahrain HARD slope > 0.03, got {cal['HARD']}"
    assert cal["_source"]["HARD"] in {"fp2", "fp2_scaled", "fp1", "fp3"}
    assert cal["_source"]["SOFT"] == "fp2"
    assert cal["SOFT"] > DEFAULT_COMPOUND_SLOPE["SOFT"]


@pytest.mark.skipif(not _fastf1_cache_ok(), reason="FastF1 cache not available")
def test_get_deg_slope_uses_weekend_calibration():
    g15 = get_deg_slope("HARD")
    weekend = get_deg_slope("HARD", circuit_id="Bahrain", year=2024, round_number=1)
    assert g15 == pytest.approx(DEFAULT_COMPOUND_SLOPE["HARD"])
    assert weekend > g15
