"""nearest_rainfall helper — FastF1 weather_data['Rainfall'] join."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from aris.physics.wet import nearest_rainfall


def test_nearest_rainfall_picks_closest_sample():
    weather = pd.DataFrame(
        {
            "Time": [timedelta(seconds=60), timedelta(seconds=180), timedelta(seconds=300)],
            "Rainfall": [False, True, False],
        }
    )
    assert nearest_rainfall(weather, timedelta(seconds=50)) is False
    assert nearest_rainfall(weather, timedelta(seconds=190)) is True
    assert nearest_rainfall(weather, timedelta(seconds=400)) is False


def test_nearest_rainfall_empty_is_dry():
    assert nearest_rainfall(None, timedelta(seconds=10)) is False
    assert nearest_rainfall(pd.DataFrame(), timedelta(seconds=10)) is False
