"""T3-E wet / intermediate heuristic — uncalibrated."""

from __future__ import annotations

from aris.field.standings import StandingRow
from aris.field.state import FieldState, ReplayIndex
from aris.narrate import narrate_recommendation
from aris.physics.wet import should_recommend_inter, should_recommend_wet
from aris.recommend import recommend
from aris.simulate import ActionKind
from tests.test_strategy import _sample_state


def _brazil_state(**kwargs):
    defaults = dict(
        country="Brazil",
        year=2024,
        round_no=21,
        lap_number=20,
        laps_remaining=51,
        total_laps=71,
        compound="MEDIUM",
        tyre_life=8,
        lag1_pace=75.0,
        track_status="1",
        weather_rainfall=True,
        rainfall_mm_per_lap=1.2,
    )
    defaults.update(kwargs)
    return _sample_state(**defaults)


def test_should_recommend_inter_on_rainfall_boolean():
    state = _brazil_state()
    assert should_recommend_inter(state) is True


def test_should_not_treat_sc_status_as_wet():
    state = _sample_state(
        compound="MEDIUM",
        laps_remaining=40,
        track_status="4",
        weather_rainfall=False,
        rainfall_mm_per_lap=None,
    )
    assert should_recommend_inter(state) is False


def test_should_not_treat_red_flag_as_wet():
    state = _brazil_state(track_status="5")
    assert should_recommend_inter(state) is False
    assert should_recommend_wet(state) is False


def test_field_car_on_inter_triggers_heuristic():
    state = _sample_state(
        compound="SOFT",
        laps_remaining=30,
        weather_rainfall=False,
        rainfall_mm_per_lap=None,
        track_status="1",
    )
    field = FieldState(
        session_id=1,
        index=ReplayIndex(20, 3),
        total_laps=57,
        standings=[
            StandingRow(
                position=1,
                driver_id=2,
                code="HAM",
                full_name="HAM",
                team="MER",
                lap_number=20,
                sector_idx=3,
                cumulative_time_s=1500.0,
                gap_to_leader_s=0.0,
                gap_ahead_s=None,
                gap_behind_s=1.0,
                last_lap_s=90.0,
                sector_1_s=30.0,
                sector_2_s=30.0,
                sector_3_s=30.0,
                compound="INTERMEDIATE",
                tyre_life=2,
                pit_in=False,
                pit_out=False,
                track_status="1",
                stint_number=2,
            )
        ],
    )
    assert should_recommend_inter(state, field) is True


def test_brazil_inter_in_shortlist_slick_not_rank_one():
    result = recommend(_brazil_state(), top_k=3, mc_draws=0)
    labels = [r.label for r in result.recommendations]
    assert any("INTERMEDIATE" in r.label for r in result.recommendations), labels
    assert result.recommendations[0].wet_heuristic is True
    top_compound = result.recommendations[0].action.pit_compound
    assert top_compound in {"INTERMEDIATE", "WET"}
    radio = narrate_recommendation(result.recommendations[0], use_llm=False)
    assert "HEURISTIC" in radio
    assert "reduced confidence" in radio.lower()


def test_already_on_inter_does_not_retrigger_inter():
    state = _brazil_state(compound="INTERMEDIATE")
    assert should_recommend_inter(state) is False


def test_dry_identity_unchanged_without_rain():
    from tests.test_circuit_deg import _zandvoort_state

    result = recommend(_zandvoort_state(), top_k=3, mc_draws=0)
    assert result.recommendations[0].wet_heuristic is False
    assert "INTERMEDIATE" not in result.recommendations[0].label
    assert result.recommendations[0].label.startswith("Pit lap 33 for HARD")
