"""Phase E1b — SC/VSC pace caveat + TrackStatus helpers."""

from __future__ import annotations

from aris.narrate import _fallback_narration
from aris.recommend import Recommendation
from aris.simulate import ActionKind, StrategyAction
from aris.state import SC_PACE_CAVEAT, track_status_is_sc_vsc


def test_track_status_sc_vsc_codes():
    assert track_status_is_sc_vsc("1") is False
    assert track_status_is_sc_vsc(None) is False
    assert track_status_is_sc_vsc("4") is True
    assert track_status_is_sc_vsc("6") is True
    assert track_status_is_sc_vsc("7") is True
    assert track_status_is_sc_vsc("24") is True  # yellow + SC
    assert track_status_is_sc_vsc("2") is False  # yellow only


def test_fallback_narration_appends_sc_caveat():
    rec = Recommendation(
        rank=1,
        label="Stay out on current tyres",
        action=StrategyAction(kind=ActionKind.STAY_OUT),
        delta_vs_stay_out_s=0.0,
        mean_race_time_s=100.0,
        confidence_std_s=0.5,
        p10_delta_s=-0.2,
        p90_delta_s=0.2,
        evidence="sim",
        narration_context={
            "driver": "VER",
            "lap": 40,
            "delta_s": 0.0,
            "confidence_caveat": SC_PACE_CAVEAT,
        },
    )
    text = _fallback_narration(rec)
    assert "Safety Car-affected" in text
    assert "lower confidence" in text
