"""Tests for pre-race strat plans."""

from aris.plan.prewrite import derive_pit_windows, generate_strat_plans
from aris.simulate import simulate_full_race
from aris.state import RaceState
from aris.tracks import clear_track_config_cache, load_track_config


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

    def test_windows_scale_with_track_length(self):
        """Monaco (78) and Belgium (44) must not share Bahrain-shaped windows."""
        clear_track_config_cache()
        monaco = load_track_config("Monaco")
        belgium = load_track_config("Belgium")
        assert monaco.total_laps >= 70
        assert belgium.total_laps <= 50

        m = derive_pit_windows(monaco.total_laps, monaco.pit_loss_s)
        b = derive_pit_windows(belgium.total_laps, belgium.pit_loss_s)

        assert m["A"][0] != b["A"][0]
        assert m["B"][0] != b["B"][0]
        assert m["A"][0] > b["A"][0]
        assert m["B"][0] > b["B"][0]
        # Monaco windows should sit well above Belgium's on a long race.
        assert m["A"][0] >= 18
        assert b["A"][0] <= 14
        assert m["C"][1] > b["C"][1]

    def test_generate_differs_monaco_vs_belgium(self):
        clear_track_config_cache()
        monaco = generate_strat_plans(
            session_id=1, driver_id=1,
            year=2024, round_no=8, country="Monaco", driver_code="VER",
            weather={"track_temp_c": 30.0},
        )
        belgium = generate_strat_plans(
            session_id=1, driver_id=1,
            year=2024, round_no=14, country="Belgium", driver_code="VER",
            weather={"track_temp_c": 25.0},
        )
        by_id_m = {p.id: p for p in monaco.plans}
        by_id_b = {p.id: p for p in belgium.plans}
        assert by_id_m["A"].pit_laps != by_id_b["A"].pit_laps
        assert by_id_m["B"].pit_laps != by_id_b["B"].pit_laps
        assert by_id_m["A"].pit_laps[0] > by_id_b["A"].pit_laps[0]
