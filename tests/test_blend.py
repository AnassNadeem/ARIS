"""Unit tests for inverse-variance forecast combination."""

from __future__ import annotations

import math

from aris.models.blend import inverse_variance_blend, rolling_error_variance


def test_inverse_variance_prefers_lower_variance_source():
    # var_a << var_b → result near pred_a
    y = inverse_variance_blend(90.0, 100.0, var_a=0.25, var_b=4.0)
    assert abs(y - 90.588235) < 1e-3


def test_inverse_variance_equal_vars_is_mean():
    y = inverse_variance_blend(10.0, 20.0, var_a=1.0, var_b=1.0)
    assert abs(y - 15.0) < 1e-9


def test_rolling_error_variance_fallback_when_short():
    assert rolling_error_variance([], fallback=2.5) == 2.5
    assert rolling_error_variance([0.1, 0.2], min_obs=3, fallback=2.5) == 2.5


def test_rolling_error_variance_sample():
    # MSE of [1,2,3] = (1+4+9)/3 — bias-aware (not sample variance=1).
    v = rolling_error_variance([1.0, 2.0, 3.0], min_obs=3)
    assert math.isclose(v, 14.0 / 3.0, rel_tol=1e-9)


def test_rolling_error_mse_penalises_bias():
    # Same scatter around different means: biased series must score worse.
    centered = rolling_error_variance([-0.5, 0.0, 0.5], min_obs=3)
    biased = rolling_error_variance([1.5, 2.0, 2.5], min_obs=3)
    assert biased > centered
    assert math.isclose(centered, (0.25 + 0.0 + 0.25) / 3.0, rel_tol=1e-9)

