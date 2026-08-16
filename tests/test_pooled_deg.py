"""Pooled context-aware tyre degradation (Phase G.4) — unit tests, no FastF1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aris.models.pooled_deg import (
    FEATURE_COLS,
    PooledDegModel,
    join_weather_nearest,
    monotonicity_at_context,
)
from aris.physics.compounds import TRUE_COMPOUND_SLOPES_ENV, parse_true_compound_mode
from aris.tracks import clear_track_config_cache, load_track_config


def test_parse_pooled_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    assert parse_true_compound_mode() == "off"
    assert parse_true_compound_mode("pooled") == "pooled"
    assert parse_true_compound_mode("g4") == "pooled"


def test_pooled_does_not_overlay_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    clear_track_config_cache()
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    assert cfg.compound_slopes["SOFT"] == pytest.approx(0.08)
    assert cfg.compound_slopes["MEDIUM"] == pytest.approx(0.05)
    assert cfg.compound_slopes["HARD"] == pytest.approx(0.03)
    clear_track_config_cache()


def test_pooled_event_overlay_opt_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(TRUE_COMPOUND_SLOPES_ENV, "pooled")
    from aris.physics import compounds as compounds_mod
    from aris.physics.compounds import clear_compound_caches

    clear_compound_caches()
    monkeypatch.setattr(
        compounds_mod,
        "load_pooled_event_slopes",
        lambda: {"2025|Netherlands|15": {"HARD": 0.02, "MEDIUM": 0.04, "SOFT": 0.09}},
    )
    clear_track_config_cache()
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    assert cfg.compound_slopes["HARD"] == pytest.approx(0.02)
    assert cfg.compound_slopes["MEDIUM"] == pytest.approx(0.04)
    assert cfg.compound_slopes["SOFT"] == pytest.approx(0.09)
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    clear_track_config_cache()


def test_weather_nearest_join_does_not_fabricate():
    laps = pd.DataFrame(
        {
            "LapStartTime": [
                pd.Timedelta(seconds=100),
                pd.Timedelta(seconds=200),
                pd.Timedelta(seconds=300),
            ],
            "LapNumber": [1, 2, 3],
        }
    )
    empty = join_weather_nearest(laps, None)
    assert empty["air_temp_c"].isna().all()

    weather = pd.DataFrame(
        {
            "Time": [pd.Timedelta(seconds=90), pd.Timedelta(seconds=210)],
            "AirTemp": [20.0, 22.0],
            "TrackTemp": [30.0, 34.0],
            "Humidity": [40.0, 42.0],
        }
    )
    joined = join_weather_nearest(laps, weather)
    assert joined.loc[0, "air_temp_c"] == pytest.approx(20.0)
    assert joined.loc[1, "air_temp_c"] == pytest.approx(22.0)
    assert joined.loc[0, "weather_delta_s"] == pytest.approx(10.0)
    assert joined["humidity_pct"].notna().all()


def test_weather_join_accepts_duplicate_index():
    idx = pd.Index([0, 0, 1])
    laps = pd.DataFrame(
        {
            "LapStartTime": [
                pd.Timedelta(seconds=100),
                pd.Timedelta(seconds=200),
                pd.Timedelta(seconds=300),
            ]
        },
        index=idx,
    )
    weather = pd.DataFrame(
        {
            "Time": [pd.Timedelta(seconds=100), pd.Timedelta(seconds=200), pd.Timedelta(seconds=300)],
            "AirTemp": [1.0, 2.0, 3.0],
            "TrackTemp": [10.0, 20.0, 30.0],
            "Humidity": [40.0, 41.0, 42.0],
        }
    )
    joined = join_weather_nearest(laps, weather)
    assert len(joined) == 3
    assert list(joined["air_temp_c"]) == [1.0, 2.0, 3.0]


def _synthetic_deg_frame(n_per: int = 40) -> pd.DataFrame:
    """C1 slope 0.02, C5 slope 0.10, same context — order is in the data."""
    rows = []
    for code, slope in (("C1", 0.02), ("C2", 0.04), ("C3", 0.06), ("C4", 0.08), ("C5", 0.10)):
        for i in range(n_per):
            life = 2 + (i % 15)
            rows.append(
                {
                    "event_id": f"ev{i % 4}",
                    "compound_id": code,
                    "era": "2023-2025",
                    "tyre_life": life,
                    "air_temp_c": 25.0,
                    "track_temp_c": 35.0,
                    "humidity_pct": 40.0,
                    "gap_to_nearest_s": 3.0,
                    "n_corners": 14.0,
                    "stint_position": 1.0,
                    "target": slope * (life - 2) + 0.01 * np.sin(i),
                }
            )
    return pd.DataFrame(rows)


def test_slope_at_fixed_context_recovers_order():
    frame = _synthetic_deg_frame()
    model = PooledDegModel(
        xgb_params={"max_depth": 3, "eta": 0.2, "seed": 42},
        num_boost_round=40,
    )
    model.fit(frame, loro=False)
    ctx = {
        "air_temp_c": 25.0,
        "track_temp_c": 35.0,
        "humidity_pct": 40.0,
        "gap_to_nearest_s": 3.0,
        "n_corners": 14.0,
        "stint_position": 1.0,
    }
    report = monotonicity_at_context(model, "2023-2025", ctx)
    slopes = report["slopes"]
    assert slopes["C1"] < slopes["C3"] < slopes["C5"]
    imps = model.feature_importances()
    assert set(FEATURE_COLS) & set(imps)
    # tyre_life or compound_id should carry signal in this toy set
    assert imps.get("tyre_life", 0) + imps.get("compound_id", 0) > 0.2


def test_feature_matrix_is_numeric_one_hot():
    from aris.models.pooled_deg import ENCODED_COLS, feature_matrix

    frame = _synthetic_deg_frame(n_per=8)
    x, y = feature_matrix(frame)
    assert list(x.columns) == list(ENCODED_COLS)
    assert x.dtypes.apply(lambda d: np.issubdtype(d, np.number)).all()
    assert not any(x[c].map(lambda v: isinstance(v, str)).any() for c in x.columns)
    assert x["compound_C1"].sum() > 0
    assert x["era_2023-2025"].sum() == len(frame)
