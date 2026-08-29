"""T9 multi-compound pit shortlist."""

from __future__ import annotations

from aris.recommend import _candidate_actions, _get_available_compounds
from aris.simulate import ActionKind
from aris.state import RaceState, load_pirelli_allocation


def _state(**kwargs) -> RaceState:
    defaults = dict(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2025,
        round_no=1,
        country="Australia",
        lap_number=15,
        compound="SOFT",
        tyre_life=12,
        fuel_kg=50.0,
        laps_remaining=42,
        total_laps=57,
        pit_compound="HARD",
    )
    defaults.update(kwargs)
    return RaceState(**defaults)


def test_pirelli_csv_loads_bahrain_2024():
    alloc = load_pirelli_allocation(2024, 1)
    assert alloc == ["SOFT", "MEDIUM", "HARD"]


def test_late_race_allows_all_dry_compounds():
    state = _state(compound="SOFT", laps_remaining=10, lap_number=47, total_laps=57)
    assert _get_available_compounds(state) == ["SOFT", "MEDIUM", "HARD"]


def test_soft_stint_suppresses_soft_when_warm():
    state = _state(compound="SOFT", laps_remaining=40, track_temp_c=28.0)
    assert "SOFT" not in _get_available_compounds(state)
    assert "HARD" in _get_available_compounds(state)


def test_soft_stint_keeps_soft_when_cold():
    state = _state(compound="SOFT", laps_remaining=40, track_temp_c=15.0)
    assert "SOFT" in _get_available_compounds(state)


def test_medium_stint_suppresses_medium_when_hot():
    state = _state(compound="MEDIUM", laps_remaining=40, track_temp_c=32.0)
    avail = _get_available_compounds(state)
    assert "MEDIUM" not in avail
    assert "HARD" in avail


def test_medium_stint_keeps_medium_without_track_temp():
    state = _state(compound="MEDIUM", laps_remaining=47, track_temp_c=None)
    assert "MEDIUM" in _get_available_compounds(state)


def test_pit_now_emits_one_candidate_per_available_compound():
    state = _state(compound="MEDIUM", laps_remaining=47, track_temp_c=None)
    actions = _candidate_actions(state)
    now = [
        a.pit_compound
        for a in actions
        if a.kind == ActionKind.PIT_NOW
    ]
    assert now == ["SOFT", "MEDIUM", "HARD"]
    lap33 = [
        a.pit_compound
        for a in actions
        if a.kind == ActionKind.PIT_LAP and a.pit_lap == state.lap_number + 8
    ]
    assert lap33 == ["SOFT", "MEDIUM", "HARD"]
