"""Tests for aris.physics.tires."""

import pandas as pd
import pytest

from aris.physics.tires import (
    DEFAULT_COMPOUND_SLOPE,
    OUT_LAP_PENALTY_S,
    blend_slope_prior,
    fit_compound_slopes,
    fit_track_compound_slopes,
    normalize_compound,
    slope_mean_var,
    tire_pace_loss,
)


class TestTirePaceLoss:
    def test_out_lap_has_cold_penalty(self):
        loss = tire_pace_loss("SOFT", 1)
        assert loss == pytest.approx(OUT_LAP_PENALTY_S)

    def test_degradation_grows_with_stint_age(self):
        assert tire_pace_loss("MEDIUM", 5) > tire_pace_loss("MEDIUM", 2)

    def test_soft_degrades_faster_than_hard(self):
        assert tire_pace_loss("SOFT", 10) > tire_pace_loss("HARD", 10)

    def test_unknown_compound_falls_back_to_medium_slope(self):
        medium = tire_pace_loss("MEDIUM", 8)
        unknown = tire_pace_loss("HYPERSOFT", 8)
        assert unknown == pytest.approx(medium)

    def test_invalid_lap_raises(self):
        with pytest.raises(ValueError, match="lap_in_stint"):
            tire_pace_loss("SOFT", 0)

    def test_custom_slopes(self):
        custom = {"SOFT": 0.2}
        assert tire_pace_loss("SOFT", 3, slopes=custom) == pytest.approx(0.2 * 2)


class TestFitCompoundSlopes:
    def test_returns_defaults_when_insufficient_data(self):
        metrics = pd.DataFrame(
            {"Compound": ["SOFT"], "DegSlope": [0.1]}
        )
        slopes = fit_compound_slopes(metrics, min_stints=3)
        assert slopes["SOFT"] == DEFAULT_COMPOUND_SLOPE["SOFT"]

    def test_overrides_when_enough_stints(self):
        metrics = pd.DataFrame(
            {
                "Compound": ["SOFT"] * 4,
                "DegSlope": [0.12, 0.11, 0.13, 0.12],
            }
        )
        slopes = fit_compound_slopes(metrics, min_stints=3)
        assert slopes["SOFT"] == pytest.approx(0.12)


def test_normalize_compound():
    assert normalize_compound("soft") == "SOFT"
    assert normalize_compound(None) == "MEDIUM"


class TestPrecisionWeightedSlopeBlend:
    def test_lower_variance_source_dominates(self):
        # prior weak (high var), obs tight → near obs
        blended = blend_slope_prior(0.10, 1.0, 0.04, 0.01)
        assert blended == pytest.approx(0.04, abs=0.01)

    def test_equal_variance_is_midpoint(self):
        blended = blend_slope_prior(0.10, 0.05, 0.00, 0.05)
        assert blended == pytest.approx(0.05)

    def test_slope_mean_var_needs_two_obs_for_sample_var(self):
        mean, var = slope_mean_var([0.1, 0.2])
        assert mean == pytest.approx(0.15)
        assert var > 0


class TestFitTrackCompoundSlopes:
    def test_low_variance_session_dominates_pool(self):
        # Noisy FP2 (high var) vs tight race — race should dominate.
        metrics = pd.DataFrame(
            {
                "Compound": ["SOFT"] * 8,
                "DegSlope": [2.0, -2.0, 1.5, -1.5, 0.09, 0.10, 0.11, 0.10],
                "SessionKey": ["2021-FP2"] * 4 + ["2021-R"] * 4,
            }
        )
        slopes = fit_track_compound_slopes(metrics, min_stints_prior=3, min_stints_session=2)
        assert slopes["SOFT"] == pytest.approx(0.10, abs=0.05)

    def test_insufficient_data_keeps_default(self):
        metrics = pd.DataFrame(
            {
                "Compound": ["SOFT", "SOFT"],
                "DegSlope": [0.2, 0.25],
                "SessionKey": ["2021-R", "2021-R"],
            }
        )
        slopes = fit_track_compound_slopes(metrics, min_stints_prior=5, min_stints_session=3)
        assert slopes["SOFT"] == DEFAULT_COMPOUND_SLOPE["SOFT"]


def test_track_override_merges_with_defaults():
    # Override SOFT only; HARD still uses global default via merge.
    custom = {"SOFT": 0.2}
    soft = tire_pace_loss("SOFT", 5, slopes=custom)
    hard = tire_pace_loss("HARD", 5, slopes=custom)
    assert soft == pytest.approx(0.2 * 4)
    assert hard == pytest.approx(DEFAULT_COMPOUND_SLOPE["HARD"] * 4)
