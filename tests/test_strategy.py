"""Unit tests for strategy engine (no DB required)."""

import pytest

from aris.montecarlo import run_mc
from aris.narrate import narrate_recommendation
from aris.recommend import recommend
from aris.simulate import ActionKind, StrategyAction, simulate
from aris.state import RaceState


def _sample_state(**kwargs) -> RaceState:
    defaults = dict(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2024,
        round_no=1,
        country="Bahrain",
        lap_number=15,
        compound="SOFT",
        tyre_life=12,
        fuel_kg=50.0,
        laps_remaining=42,
        lag1_pace=94.5,
        lag2_pace=94.3,
        stint_roll3=94.4,
        pit_compound="HARD",
    )
    defaults.update(kwargs)
    return RaceState(**defaults)


class TestSimulate:
    def test_stay_out_returns_positive_time(self):
        outcome = simulate(_sample_state(), StrategyAction(kind=ActionKind.STAY_OUT))
        assert outcome.total_race_time_s > 0
        assert outcome.delta_vs_stay_out_s == 0.0

    def test_pit_now_differs_from_stay_out(self):
        stay = simulate(_sample_state(), StrategyAction(kind=ActionKind.STAY_OUT))
        pit = simulate(
            _sample_state(),
            StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="HARD"),
        )
        assert pit.total_race_time_s != stay.total_race_time_s

    def test_evolving_lags_changes_over_laps(self):
        outcome = simulate(_sample_state(lap_number=5, laps_remaining=52), StrategyAction(kind=ActionKind.STAY_OUT))
        assert outcome.laps_simulated == 53

    def test_lift_t7_slower_than_stay_out(self):
        stay = simulate(_sample_state(), StrategyAction(kind=ActionKind.STAY_OUT))
        lift = simulate(
            _sample_state(),
            StrategyAction(kind=ActionKind.LIFT, corner_index=7, distance_m=30.0),
        )
        assert lift.delta_vs_stay_out_s > 0.0
        assert lift.total_race_time_s > stay.total_race_time_s
        assert "lift" in lift.evidence.lower()


class TestRecommend:
    def test_returns_top_three(self):
        result = recommend(_sample_state(), top_k=3, mc_draws=20)
        assert len(result.recommendations) == 3
        assert result.recommendations[0].rank == 1

    def test_stay_out_always_in_candidates(self):
        result = recommend(_sample_state(), top_k=10, mc_draws=10)
        labels = [r.label for r in result.recommendations]
        assert any("stay" in lbl.lower() for lbl in labels)

    def test_mc_draws_zero_uses_extrapolation_std_not_mc(self):
        result = recommend(_sample_state(), top_k=3, mc_draws=0)
        assert len(result.recommendations) == 3
        assert result.recommendations[0].rank == 1
        from aris.simulate import extrapolation_std_s

        for rec in result.recommendations:
            assert rec.confidence_std_s == extrapolation_std_s(
                rec.extrapolation_beyond_laps
            )


class TestPhysicsDeltaRollout:
    def test_later_laps_follow_physics_delta_not_chained_residual(self):
        from aris.models.features import estimate_fuel_kg
        from aris.models.predict import predict_lap_time, predict_physics
        from aris.tracks import load_track_config

        state = _sample_state(
            lap_number=56, laps_remaining=1, total_laps=57, tyre_life=10
        )
        outcome = simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))
        assert outcome.laps_simulated == 2
        track = load_track_config(
            state.country, year=state.year, round_no=state.round_no
        ).load_physics()
        fuel0 = estimate_fuel_kg(56, total_laps=57)
        fuel1 = estimate_fuel_kg(57, total_laps=57)
        pred0 = predict_lap_time(
            compound=state.compound,
            tyre_life=10,
            fuel_kg=fuel0,
            track=track,
            lag1_pace=state.lag1_pace,
            lag2_pace=state.lag2_pace,
            stint_roll3=state.stint_roll3,
        )
        phys0 = predict_physics(
            compound=state.compound, tyre_life=10, fuel_kg=fuel0, track=track
        )
        phys1 = predict_physics(
            compound=state.compound, tyre_life=11, fuel_kg=fuel1, track=track
        )
        expected = pred0 + (pred0 + (phys1 - phys0))
        assert abs(outcome.total_race_time_s - expected) < 1e-6

    def test_long_remaining_hard_pit_beats_soft_pit(self):
        """G1.3: residual-on-fake-lags preferred SOFT over HARD; physics-delta should not."""
        state = _sample_state()
        hard = simulate(
            state, StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="HARD")
        )
        soft = simulate(
            state, StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="SOFT")
        )
        assert hard.total_race_time_s < soft.total_race_time_s


class TestExtrapolation:
    def test_soft_long_stint_sets_caveat(self):
        state = _sample_state(compound="SOFT", tyre_life=12, laps_remaining=42)
        pit = simulate(
            state, StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="SOFT")
        )
        assert pit.extrapolation_beyond_laps > 0
        assert pit.extrapolation_compound == "SOFT"
        assert pit.extrapolation_caveat is not None
        assert "beyond typical observed stints" in pit.extrapolation_caveat
        assert "lower confidence" in pit.extrapolation_caveat

    def test_discount_shrinks_pit_delta_when_beyond_ceiling(self):
        from aris.simulate import extrapolation_weight

        state = _sample_state(compound="SOFT", tyre_life=12, laps_remaining=42)
        raw = simulate(
            state, StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="SOFT")
        )
        w = extrapolation_weight(raw.extrapolation_beyond_laps)
        assert raw.extrapolation_beyond_laps > 0
        assert w < 1.0
        ranked = recommend(state, top_k=3, mc_draws=0)
        extra = [r for r in ranked.recommendations if r.extrapolation_beyond_laps > 0]
        assert extra
        for rec in extra:
            assert rec.extrapolation_weight == extrapolation_weight(
                rec.extrapolation_beyond_laps
            )
            assert rec.extrapolation_weight <= 1.0

    def test_recommend_surfaces_caveat_like_sc(self):
        from aris.state import SC_PACE_CAVEAT
        from aris.ui_text import recommendation_caveat

        state = _sample_state(
            compound="SOFT",
            tyre_life=12,
            laps_remaining=42,
            confidence_caveat=SC_PACE_CAVEAT,
            recent_sc_pace=True,
        )
        result = recommend(state, top_k=3, mc_draws=0)
        top = result.recommendations[0]
        text = recommendation_caveat(top.narration_context, top.evidence)
        assert text is not None
        assert "lower confidence" in text
        # Both SC and (when the top action extrapolates) stint-length notes.
        assert "Safety Car-affected" in text or "beyond typical observed" in text


class TestUndercutBonus:
    def test_gap_21s_base_only(self):
        from aris.recommend import compute_undercut_bonus

        state = _sample_state(gap_ahead_s=21.0, gap_ahead_history=[])
        assert compute_undercut_bonus(state) == -0.3

    def test_gap_0_8s_drs_extra(self):
        from aris.recommend import compute_undercut_bonus

        state = _sample_state(gap_ahead_s=0.8, gap_ahead_history=[])
        assert compute_undercut_bonus(state) == -0.6

    def test_closing_adds_and_caps(self):
        from aris.recommend import compute_undercut_bonus

        state = _sample_state(
            gap_ahead_s=0.8,
            gap_ahead_history=[1.1, 0.95, 0.8],  # closing 0.3/3 = 0.1 > 0.05
        )
        assert compute_undercut_bonus(state) == -0.8

    def test_opening_reduces_urgency(self):
        from aris.recommend import compute_undercut_bonus

        state = _sample_state(
            gap_ahead_s=5.0,
            gap_ahead_history=[4.7, 4.85, 5.0],  # opening -0.3/3 = -0.1
        )
        assert compute_undercut_bonus(state) == pytest.approx(-0.2)  # -0.3 + 0.1

    def test_no_history_no_trend(self):
        from aris.recommend import compute_undercut_bonus

        state = _sample_state(gap_ahead_s=5.0, gap_ahead_history=[])
        assert compute_undercut_bonus(state) == -0.3

    def test_outside_window_zero(self):
        from aris.recommend import compute_undercut_bonus

        assert compute_undercut_bonus(_sample_state(gap_ahead_s=22.0)) == 0.0
        assert compute_undercut_bonus(_sample_state(gap_ahead_s=0.0)) == 0.0
        assert compute_undercut_bonus(_sample_state(gap_ahead_s=None)) == 0.0

    def test_recommend_surfaces_undercut_evidence(self):
        state = _sample_state(gap_ahead_s=0.8, gap_ahead_history=[])
        result = recommend(state, top_k=3, mc_draws=0)
        pit = next(
            r
            for r in result.recommendations
            if r.action.kind != ActionKind.STAY_OUT or r.action.pit_laps
        )
        assert "undercut bonus active" in pit.evidence.lower()
        stay = [
            r
            for r in result.recommendations
            if r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps
        ]
        assert stay, "stay-out must remain in top-3"


class TestMonteCarlo:
    def test_distribution_has_std(self):
        state = _sample_state()
        action = StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="HARD")
        dist = run_mc(state, action, n_draws=30, seed=1)
        assert dist.n_draws == 30
        assert dist.std_time_s >= 0


class TestNarrate:
    def test_fallback_without_llm(self):
        result = recommend(_sample_state(), top_k=1, mc_draws=5)
        text = narrate_recommendation(result.recommendations[0], use_llm=False)
        assert "VER" in text or "ver" in text.lower()
        assert len(text) > 10
