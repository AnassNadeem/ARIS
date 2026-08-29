"""T3-E wet / intermediate heuristic — uncalibrated."""

from __future__ import annotations

from aris.field.standings import StandingRow
from aris.field.state import FieldState, ReplayIndex
from aris.narrate import narrate_recommendation
from aris.physics.wet import (
    should_recommend_inter,
    should_recommend_wet,
    should_stay_on_wet,
    wet_stay_delta,
)
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
        rainfall=True,
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
        rainfall=False,
        weather_rainfall=False,
        rainfall_mm_per_lap=None,
    )
    assert should_recommend_inter(state, "4") is False


def test_dry_sc_does_not_recommend_inter_card():
    state = _sample_state(
        country="Netherlands",
        year=2025,
        round_no=15,
        lap_number=30,
        total_laps=72,
        laps_remaining=42,
        compound="MEDIUM",
        tyre_life=15,
        lag1_pace=73.0,
        lag2_pace=73.2,
        stint_roll3=73.1,
        gap_ahead_s=3.0,
        track_status="4",
        rainfall=False,
    )
    result = recommend(state, top_k=3, mc_draws=0)
    compounds = [r.action.pit_compound or "-" for r in result.recommendations]
    assert "INTERMEDIATE" not in compounds
    assert not any(r.wet_heuristic for r in result.recommendations)


def test_wet_race_recommends_inter_card():
    state = _brazil_state(
        lap_number=40,
        total_laps=71,
        laps_remaining=31,
        tyre_life=20,
        lag1_pace=82.0,
        lag2_pace=82.5,
        stint_roll3=82.2,
        track_status="1",
        rainfall=True,
    )
    result = recommend(state, top_k=3, mc_draws=0)
    compounds = [r.action.pit_compound or "-" for r in result.recommendations]
    assert "INTERMEDIATE" in compounds
    assert result.recommendations[0].wet_heuristic is True


def test_should_not_treat_red_flag_as_wet():
    state = _brazil_state(track_status="5")
    assert should_recommend_inter(state) is False
    assert should_recommend_wet(state) is False


def test_field_car_on_inter_is_not_a_rain_signal():
    state = _sample_state(
        compound="SOFT",
        laps_remaining=30,
        rainfall=False,
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
    assert should_recommend_inter(state, field=field) is False


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
    assert should_stay_on_wet(state) is True


def test_already_on_inter_in_rain_does_not_rank_dry_pit():
    state = _brazil_state(
        driver_code="LEC",
        lap_number=28,
        total_laps=71,
        laps_remaining=43,
        compound="INTERMEDIATE",
        tyre_life=4,
        lag1_pace=87.5,
        lag2_pace=88.1,
        stint_roll3=87.8,
        gap_ahead_s=5.0,
        track_status="1",
        fuel_kg=61.6,
        pit_compound="HARD",
        rainfall=True,
    )
    result = recommend(state, mc_draws=0)
    dry = {"SOFT", "MEDIUM", "HARD"}
    top = result.recommendations[0]
    assert top.action.pit_compound not in dry
    assert top.action.kind == ActionKind.STAY_OUT


def test_session_rain_on_inter_does_not_rank_dry_pit():
    """Per-lap Rainfall can be False while the car is still on INTER in a wet session."""
    state = _brazil_state(
        driver_code="LEC",
        lap_number=27,
        total_laps=71,
        laps_remaining=44,
        compound="INTERMEDIATE",
        tyre_life=8,
        track_status="4",
        rainfall=False,
        weather_rainfall=True,
    )
    result = recommend(state, mc_draws=0)
    dry = {"SOFT", "MEDIUM", "HARD"}
    assert result.recommendations[0].action.pit_compound not in dry
    assert result.recommendations[0].action.kind == ActionKind.STAY_OUT
    state = _sample_state(
        driver_code="VER",
        country="Netherlands",
        year=2025,
        round_no=15,
        lap_number=30,
        total_laps=72,
        laps_remaining=42,
        compound="INTERMEDIATE",
        tyre_life=5,
        lag1_pace=81.0,
        lag2_pace=81.5,
        stint_roll3=81.2,
        gap_ahead_s=3.0,
        track_status="4",
        fuel_kg=59.1,
        rainfall=False,
        weather_rainfall=False,
        rainfall_mm_per_lap=None,
    )
    result = recommend(state, mc_draws=0)
    dry = {"SOFT", "MEDIUM", "HARD"}
    assert result.recommendations[0].action.pit_compound in dry


def test_should_stay_on_wet_guards():
    raining = _brazil_state(compound="INTERMEDIATE")
    assert should_stay_on_wet(raining) is True
    assert should_stay_on_wet(_brazil_state(compound="MEDIUM")) is False
    assert should_stay_on_wet(
        _brazil_state(compound="INTERMEDIATE", rainfall=False, weather_rainfall=False)
    ) is False
    assert should_stay_on_wet(
        _brazil_state(compound="INTERMEDIATE", rainfall=False, weather_rainfall=True)
    ) is True
    assert should_stay_on_wet(_brazil_state(compound="INTERMEDIATE", track_status="5")) is False
    assert should_stay_on_wet(
        _brazil_state(compound="INTERMEDIATE", laps_remaining=3, lap_number=68)
    ) is False
    assert wet_stay_delta(raining, 10) == 15.0


def test_dry_identity_unchanged_without_rain():
    from tests.test_circuit_deg import _zandvoort_state

    result = recommend(_zandvoort_state(), top_k=3, mc_draws=0)
    assert result.recommendations[0].wet_heuristic is False
    assert "INTERMEDIATE" not in result.recommendations[0].label
    assert result.recommendations[0].label.startswith("Pit lap 33 for HARD")


def test_damp_single_tick_rain_does_not_recommend_inter():
    from tests.test_circuit_deg import _zandvoort_state

    state = _zandvoort_state().model_copy(
        update={
            "track_state": "DAMP",
            "rainfall": True,
            "weather_rainfall": False,
            "rainfall_mm_per_lap": None,
            "tyre_life": 18,
        }
    )
    result = recommend(state, top_k=3, mc_draws=0)
    assert not any(
        (r.action.pit_compound or "") == "INTERMEDIATE" and r.wet_heuristic
        for r in result.recommendations
    ), [r.label for r in result.recommendations]
