"""Unit tests for strategy engine (no DB required)."""

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


class TestRecommend:
    def test_returns_top_three(self):
        result = recommend(_sample_state(), top_k=3, mc_draws=20)
        assert len(result.recommendations) == 3
        assert result.recommendations[0].rank == 1

    def test_stay_out_always_in_candidates(self):
        result = recommend(_sample_state(), top_k=10, mc_draws=10)
        labels = [r.label for r in result.recommendations]
        assert any("stay" in lbl.lower() for lbl in labels)


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
