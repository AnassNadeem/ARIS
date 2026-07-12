"""Tests for pre-race strat plans."""

from aris.plan.prewrite import generate_strat_plans
from aris.simulate import simulate_full_race
from aris.state import RaceState


class TestPrewrite:
    def test_generate_three_plans(self):
        plans = generate_strat_plans(
            session_id=1, driver_id=1,
            year=2024, round_no=1, country="Bahrain", driver_code="VER",
            weather={"track_temp_c": 35.0},
        )
        assert len(plans.plans) == 3
        assert any(p.recommended for p in plans.plans)

    def test_simulate_full_race(self):
        state = RaceState(
            session_id=1, driver_id=1, driver_code="VER", driver_name="Max",
            year=2024, round_no=1, country="Bahrain",
            lap_number=1, compound="MEDIUM", tyre_life=1,
            fuel_kg=110.0, laps_remaining=56, total_laps=57,
        )
        t = simulate_full_race(state, pit_laps=[20], pit_compounds=["HARD"])
        assert t > 0
