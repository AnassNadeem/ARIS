"""Tests for aris.physics.tires."""

import pandas as pd
import pytest

from aris.physics.tires import (
    DEFAULT_COMPOUND_SLOPE,
    OUT_LAP_PENALTY_S,
    fit_compound_slopes,
    normalize_compound,
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
