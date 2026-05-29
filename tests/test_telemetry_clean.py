"""Unit tests for the telemetry gear-cleaning rule (no database needed)."""

from __future__ import annotations

import numpy as np
import pytest

from aris.io.ingest import _clean_gear


@pytest.mark.parametrize("gear", [1, 2, 3, 4, 5, 6, 7, 8])
def test_valid_gears_pass_through(gear):
    assert _clean_gear(gear) == gear


@pytest.mark.parametrize("bad", [0, -1, 9, 17, 47, 75])
def test_out_of_range_gears_become_none(bad):
    assert _clean_gear(bad) is None


def test_missing_gear_becomes_none():
    assert _clean_gear(np.nan) is None
    assert _clean_gear(None) is None


def test_float_in_range_is_coerced_to_int():
    assert _clean_gear(5.0) == 5
