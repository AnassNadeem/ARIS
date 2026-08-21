"""T3-A rival pit-lap estimates — infrastructure, not match-rate."""

from __future__ import annotations

from aris.field.rivals import (
    RivalState,
    estimate_all_rivals,
    estimate_rival_pit_lap,
)
from aris.field.standings import StandingRow
from aris.field.state import FieldState, ReplayIndex


def _row(
    *,
    position: int,
    code: str,
    compound: str = "MEDIUM",
    tyre_life: int = 20,
    gap_to_leader_s: float = 0.0,
    last_lap_s: float = 74.0,
    stint_number: int = 1,
    driver_id: int | None = None,
) -> StandingRow:
    return StandingRow(
        position=position,
        driver_id=driver_id if driver_id is not None else position,
        code=code,
        full_name=code,
        team="Team",
        lap_number=20,
        sector_idx=3,
        cumulative_time_s=1500.0 + gap_to_leader_s,
        gap_to_leader_s=gap_to_leader_s,
        gap_ahead_s=None if position == 1 else 1.0,
        gap_behind_s=1.0,
        last_lap_s=last_lap_s,
        sector_1_s=25.0,
        sector_2_s=25.0,
        sector_3_s=24.0,
        compound=compound,
        tyre_life=tyre_life,
        pit_in=False,
        pit_out=False,
        track_status="1",
        stint_number=stint_number,
    )


def _nl_field(*rows: StandingRow) -> FieldState:
    return FieldState(
        session_id=1,
        index=ReplayIndex(20, 3),
        total_laps=72,
        standings=list(rows),
    )


def test_ver_medium_lap20_pits_between_22_and_30():
    rival = RivalState(
        driver_code="VER",
        position=1,
        compound="MEDIUM",
        tyre_life=20,
        gap_to_focus=1.5,
        gap_trend=0.0,
        team="Red Bull",
        last_lap_s=74.0,
    )
    est = estimate_rival_pit_lap(rival, current_lap=20, total_laps=72, circuit_key="netherlands")
    assert 22 <= est.estimated_pit_lap <= 30, est
    assert est.laps_until_pit == est.estimated_pit_lap - 20
    assert est.confidence in {"HIGH", "MEDIUM", "LOW"}


def test_zero_tyre_life_does_not_crash():
    rival = RivalState(
        driver_code="PIA",
        position=2,
        compound="SOFT",
        tyre_life=0,
        gap_to_focus=-2.0,
        gap_trend=0.0,
        team="McLaren",
        last_lap_s=73.5,
    )
    est = estimate_rival_pit_lap(rival, current_lap=20, total_laps=72, circuit_key="netherlands")
    assert est.tyre_life == 1
    assert 21 <= est.estimated_pit_lap <= 70


def test_two_car_field_does_not_crash():
    field = _nl_field(
        _row(position=1, code="NOR", gap_to_leader_s=0.0),
        _row(position=2, code="VER", gap_to_leader_s=1.2, tyre_life=20),
    )
    estimates = estimate_all_rivals(
        field, "NOR", current_lap=20, total_laps=72, circuit_key="netherlands"
    )
    assert len(estimates) == 1
    assert estimates[0].driver_code == "VER"
    assert 22 <= estimates[0].estimated_pit_lap <= 30


def test_excludes_focus_and_caps_at_six_sorted_by_pit_lap():
    rows = [
        _row(position=1, code="NOR", gap_to_leader_s=0.0, tyre_life=5, compound="HARD"),
        _row(position=2, code="VER", gap_to_leader_s=1.0, tyre_life=28, compound="MEDIUM"),
        _row(position=3, code="PIA", gap_to_leader_s=2.0, tyre_life=10, compound="MEDIUM"),
        _row(position=4, code="LEC", gap_to_leader_s=3.0, tyre_life=22, compound="MEDIUM"),
        _row(position=5, code="HAM", gap_to_leader_s=4.0, tyre_life=8, compound="HARD"),
        _row(position=6, code="RUS", gap_to_leader_s=5.0, tyre_life=15, compound="MEDIUM"),
        _row(position=7, code="SAI", gap_to_leader_s=6.0, tyre_life=12, compound="SOFT"),
        _row(position=8, code="ALO", gap_to_leader_s=7.0, tyre_life=4, compound="HARD"),
    ]
    estimates = estimate_all_rivals(
        _nl_field(*rows), "NOR", current_lap=20, total_laps=72, circuit_key="netherlands"
    )
    codes = [e.driver_code for e in estimates]
    assert "NOR" not in codes
    assert len(estimates) == 6
    assert codes == [e.driver_code for e in sorted(estimates, key=lambda e: e.estimated_pit_lap)]


def test_two_stop_reasoning_when_stint_number_ge_2():
    rival = RivalState(
        driver_code="LEC",
        position=3,
        compound="HARD",
        tyre_life=6,
        gap_to_focus=-4.0,
        gap_trend=0.0,
        team="Ferrari",
        last_lap_s=74.2,
        stint_number=2,
    )
    est = estimate_rival_pit_lap(rival, current_lap=20, total_laps=72, circuit_key="netherlands")
    assert "two-stop" in est.reasoning.lower() or "later stint" in est.reasoning.lower()


def test_estimate_clamped_to_remaining_race():
    rival = RivalState(
        driver_code="HAM",
        position=4,
        compound="SOFT",
        tyre_life=1,
        gap_to_focus=0.0,
        gap_trend=0.0,
        team="Mercedes",
        last_lap_s=74.0,
    )
    est = estimate_rival_pit_lap(rival, current_lap=70, total_laps=72, circuit_key="netherlands")
    assert est.estimated_pit_lap == 71
    assert est.laps_until_pit == 1


def test_observed_deg_pits_sooner_than_prior():
    rival = RivalState(
        driver_code="VER",
        position=1,
        compound="MEDIUM",
        tyre_life=10,
        gap_to_focus=1.0,
        gap_trend=0.0,
        team="Red Bull",
        last_lap_s=76.0,
        lap_times_history=[74.0, 74.8, 75.6, 76.4, 77.2],  # 0.8 s/lap
    )
    prior = estimate_rival_pit_lap(
        RivalState(
            driver_code="VER",
            position=1,
            compound="MEDIUM",
            tyre_life=10,
            gap_to_focus=1.0,
            gap_trend=0.0,
            team="Red Bull",
            last_lap_s=76.0,
        ),
        current_lap=20,
        total_laps=72,
        circuit_key="netherlands",
    )
    obs = estimate_rival_pit_lap(rival, current_lap=20, total_laps=72, circuit_key="netherlands")
    assert obs.estimated_pit_lap < prior.estimated_pit_lap
    assert "obs deg" in obs.reasoning
    assert "G1.5 prior" in prior.reasoning
