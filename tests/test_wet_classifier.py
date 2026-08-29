"""T10-C — rule-based wet / track-state classifier."""

from __future__ import annotations

from aris.physics.tires import normalize_compound
from aris.recommend import _get_available_compounds
from aris.risk.wet_classifier import classify_track_state_rules
from tests.test_strategy import _sample_state


def test_dry_race_returns_dry():
    label, conf = classify_track_state_rules(
        rain_flag=False,
        rain_laps_last_5=0,
        track_temp_c=30.0,
        inter_on_track=False,
        inter_pace_advantage_s=0.0,
    )
    assert label == "DRY"
    assert conf > 0.85


def test_heavy_rain_returns_wet():
    label, conf = classify_track_state_rules(
        rain_flag=True,
        rain_laps_last_5=5,
        track_temp_c=20.0,
        inter_on_track=True,
        inter_pace_advantage_s=3.0,
    )
    assert label == "WET"
    assert conf >= 0.80


def test_drying_track():
    label, _conf = classify_track_state_rules(
        rain_flag=False,
        rain_laps_last_5=0,
        track_temp_c=28.0,
        inter_on_track=True,
        inter_pace_advantage_s=0.0,
    )
    assert label == "DRYING"


def test_available_compounds_crossover():
    state = _sample_state(
        compound="MEDIUM",
        track_state="CROSSOVER",
        track_state_confidence=0.60,
        laps_remaining=40,
        total_laps=57,
        lap_number=17,
    )
    compounds = {normalize_compound(c) for c in _get_available_compounds(state)}
    assert "INTERMEDIATE" in compounds


def test_available_compounds_dry():
    state = _sample_state(
        compound="MEDIUM",
        track_state="DRY",
        track_state_confidence=0.95,
        laps_remaining=40,
        total_laps=57,
        lap_number=17,
        rainfall=False,
    )
    compounds = {normalize_compound(c) for c in _get_available_compounds(state)}
    assert "INTERMEDIATE" not in compounds
    assert "INTER" not in compounds
    assert "WET" not in compounds
