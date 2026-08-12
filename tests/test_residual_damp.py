"""Tests for residual damping when physics already matches recent pace (E3.3)."""

from __future__ import annotations

import pytest

from aris.models.predict import damp_residual_toward_pace


class TestDampResidualTowardPace:
    def test_full_residual_when_physics_far_from_pace(self):
        assert damp_residual_toward_pace(100.0, 80.0, -15.0, agree_s=8.0) == pytest.approx(-15.0)

    def test_zero_residual_when_physics_matches_pace(self):
        assert damp_residual_toward_pace(84.0, 84.0, -8.0, agree_s=8.0) == pytest.approx(0.0)

    def test_scales_linearly_inside_agree_band(self):
        # |phys - lag1| = 4, agree_s = 8 → scale 0.5
        assert damp_residual_toward_pace(88.0, 84.0, -8.0, agree_s=8.0) == pytest.approx(-4.0)

    def test_none_lag_passes_through(self):
        assert damp_residual_toward_pace(90.0, None, -5.0) == pytest.approx(-5.0)
