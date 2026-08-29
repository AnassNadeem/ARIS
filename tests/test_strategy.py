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
        from aris.simulate import _track_for

        state = _sample_state(
            lap_number=56, laps_remaining=1, total_laps=57, tyre_life=10
        )
        outcome = simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))
        assert outcome.laps_simulated == 2
        # Same slope overlay simulate() uses (T9 FP2 calibration).
        track = _track_for(state)
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
        from aris.simulate import fuel_correction_s

        d0 = phys0 - fuel_correction_s(fuel0)
        d1 = phys1 - fuel_correction_s(fuel1)
        expected = pred0 + (pred0 + (d1 - d0))
        assert abs(outcome.total_race_time_s - expected) < 1e-6

    def test_fresh_stint_adds_warmup_to_first_two_laps(self):
        from aris.models.features import estimate_fuel_kg
        from aris.models.predict import predict_lap_time, predict_physics
        from aris.physics.tyre_warmup import tyre_warmup_lap1, tyre_warmup_lap2
        from aris.simulate import _track_for

        state = _sample_state(
            lap_number=56, laps_remaining=1, total_laps=57, tyre_life=1, compound="HARD"
        )
        outcome = simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))
        track = _track_for(state)
        fuel0 = estimate_fuel_kg(56, total_laps=57)
        fuel1 = estimate_fuel_kg(57, total_laps=57)
        pred0 = predict_lap_time(
            compound="HARD",
            tyre_life=1,
            fuel_kg=fuel0,
            track=track,
            lag1_pace=state.lag1_pace,
            lag2_pace=state.lag2_pace,
            stint_roll3=state.stint_roll3,
        )
        phys0 = predict_physics(
            compound="HARD", tyre_life=1, fuel_kg=fuel0, track=track
        )
        phys1 = predict_physics(
            compound="HARD", tyre_life=2, fuel_kg=fuel1, track=track
        )
        from aris.simulate import fuel_correction_s

        d0 = phys0 - fuel_correction_s(fuel0)
        d1 = phys1 - fuel_correction_s(fuel1)
        expected = (
            pred0
            + tyre_warmup_lap1("HARD")
            + (pred0 + (d1 - d0))
            + tyre_warmup_lap2("HARD")
        )
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

    def test_short_remaining_medium_can_beat_hard(self):
        """Fresh MEDIUM pace offset should win a short final stint vs HARD slope."""
        state = _sample_state(
            lap_number=50, laps_remaining=7, total_laps=57, tyre_life=20
        )
        hard = simulate(
            state, StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="HARD")
        )
        medium = simulate(
            state, StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="MEDIUM")
        )
        assert medium.total_race_time_s < hard.total_race_time_s

    def test_fuel_deg_correction_unmasks_drop_on_long_remainder(self):
        state = _sample_state(lap_number=8, laps_remaining=49, total_laps=57)
        with_corr = simulate(
            state,
            StrategyAction(kind=ActionKind.STAY_OUT),
            fuel_deg_correction=True,
        )
        without = simulate(
            state,
            StrategyAction(kind=ActionKind.STAY_OUT),
            fuel_deg_correction=False,
        )
        assert with_corr.total_race_time_s > without.total_race_time_s


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


class TestInferFocusCompound:
    """Unit tests for _infer_focus_compound() in isolation."""

    def _call(self, stints, race_frac=0.4, laps_remaining=30):
        from aris.recommend import _infer_focus_compound
        state = _sample_state(laps_remaining=laps_remaining)
        return _infer_focus_compound(state, stints, race_frac)

    def test_empty_stints_falls_back_to_state_pit_compound(self):
        result = self._call([])
        assert result == "HARD"

    def test_soft_only_returns_hard(self):
        # SOFT-only: HARD is the dominant 2nd-stint compound; returning MEDIUM
        # broke 2024 correct HARD matches.
        stints = [{"compound": "SOFT", "lap_start": 1}]
        assert self._call(stints, race_frac=0.30) == "HARD"
        assert self._call(stints, race_frac=0.60) == "HARD"

    def test_medium_only_early_long_returns_medium(self):
        stints = [{"compound": "MEDIUM", "lap_start": 1}]
        assert self._call(stints, race_frac=0.25, laps_remaining=40) == "MEDIUM"

    def test_medium_only_early_short_returns_hard(self):
        stints = [{"compound": "MEDIUM", "lap_start": 1}]
        assert self._call(stints, race_frac=0.30, laps_remaining=20) == "HARD"

    def test_medium_only_late_returns_hard(self):
        stints = [{"compound": "MEDIUM", "lap_start": 1}]
        assert self._call(stints, race_frac=0.65) == "HARD"

    def test_year_gate_2024_no_inference(self):
        """Year gate: inference is off for 2024 — state.pit_compound unchanged."""
        from aris.recommend import recommend
        # 2024 state with MEDIUM stints that would infer MEDIUM in 2025
        state = _sample_state(
            year=2024, lap_number=15, total_laps=57,
            compound="MEDIUM", laps_remaining=40, pit_compound="HARD",
            stints={"VER": [{"lap_start": 1, "compound": "MEDIUM"}]},
        )
        result = recommend(state, top_k=3, mc_draws=0)
        # Year=2024: compound inference is off, pit_compound stays HARD
        pit = next((r for r in result.recommendations if r.action.pit_compound), None)
        assert pit is None or any(
            "HARD" in (r.action.pit_compound or "") for r in result.recommendations
        ), "2024 must not change compound to MEDIUM via inference"

    def test_hard_only_returns_medium(self):
        stints = [{"compound": "HARD", "lap_start": 1}]
        assert self._call(stints) == "MEDIUM"

    def test_soft_plus_medium_returns_hard(self):
        stints = [{"compound": "SOFT", "lap_start": 1}, {"compound": "MEDIUM", "lap_start": 20}]
        assert self._call(stints) == "HARD"

    def test_soft_plus_hard_returns_medium(self):
        stints = [{"compound": "SOFT", "lap_start": 1}, {"compound": "HARD", "lap_start": 20}]
        assert self._call(stints) == "MEDIUM"

    def test_medium_plus_hard_returns_soft(self):
        stints = [{"compound": "MEDIUM", "lap_start": 1}, {"compound": "HARD", "lap_start": 20}]
        assert self._call(stints) == "SOFT"


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


def _plan_pit_laps(rec) -> list[int]:
    action = rec.action
    pits = list(action.pit_laps or [])
    if not pits and action.pit_lap is not None:
        pits = [int(action.pit_lap)]
    if not pits and str(action.kind).lower() in {"actionkind.pit_now", "pit_now"}:
        pits = [int(rec.narration_context.get("lap") or 0)]
    return pits


def test_72_lap_ver_does_not_fabricate_two_stop():
    state = _sample_state(
        driver_code="VER",
        country="Netherlands",
        year=2025,
        round_no=15,
        lap_number=1,
        total_laps=72,
        laps_remaining=71,
        compound="MEDIUM",
        tyre_life=1,
        lag1_pace=74.0,
        lag2_pace=74.0,
        stint_roll3=74.0,
        track_state="DRY",
        rainfall=False,
        weather_rainfall=False,
        rainfall_mm_per_lap=None,
    )
    result = recommend(state, top_k=5, mc_draws=0)
    top = result.recommendations[0]
    pits = _plan_pit_laps(top)
    assert len(pits) <= 1, top.label
    assert "L31" not in top.label and "L46" not in top.label, top.label
    for rec in result.recommendations:
        assert len(_plan_pit_laps(rec)) <= 1, rec.label
