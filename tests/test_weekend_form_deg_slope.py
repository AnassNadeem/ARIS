"""weekend_form DegSlope must be a real slope (s/lap), not Pearson r."""

import pandas as pd

from aris.plan.weekend_form import _deg_slope


def test_deg_slope_is_polyfit_not_correlation():
    # Perfect linear: LapTimeS = 80 + 0.1 * tyre_life
    laps = pd.DataFrame(
        {
            "lap_time_s": [80.1, 80.2, 80.3, 80.4, 80.5],
            "tyre_life": [1, 2, 3, 4, 5],
        }
    )
    slope = _deg_slope(laps)
    assert slope is not None
    assert abs(slope - 0.1) < 1e-9
    # Pearson r would be ~1.0 — ensure we did not return that.
    assert abs(slope - 1.0) > 0.5


def test_deg_slope_none_when_too_few():
    laps = pd.DataFrame({"lap_time_s": [80.0, 80.1], "tyre_life": [1, 2]})
    assert _deg_slope(laps) is None
