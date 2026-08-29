"""T12 — degradation curve (bicycle predicted vs FastF1 actual)."""

from __future__ import annotations

from aris.explain.degradation import get_degradation_curve
from aris.explain.session import set_bundle_override
from tests.fixtures.explain_zandvoort import zandvoort_2025_bundle


def setup_function() -> None:
    set_bundle_override(zandvoort_2025_bundle())


def teardown_function() -> None:
    set_bundle_override(None)


def test_zandvoort_ver_stint1_arrays_align():
    result = get_degradation_curve("VER", stint_id=1, session_id="2025-15-R")
    ages = result["tyre_age"]
    pred = result["predicted_deg_s"]
    actual = result["actual_deg_s"]
    assert ages, "expected non-empty tyre_age for VER stint 1"
    assert len(ages) == len(pred) == len(actual)
    assert result["compound"] == "MEDIUM"
    assert result["circuit"] == "Netherlands"
    assert result["stint_id"] == 1
    assert all(a >= 1 for a in ages)


def test_predicted_increases_with_age_after_outlap():
    result = get_degradation_curve("VER", stint_id=1, session_id="2025-15-R")
    flying = [
        (age, pred)
        for age, pred in zip(result["tyre_age"], result["predicted_deg_s"])
        if age >= 3
    ]
    assert len(flying) >= 2
    assert flying[-1][1] >= flying[0][1]
