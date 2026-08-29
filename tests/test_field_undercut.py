"""T3-B field-aware undercut — gated behind ARIS_FIELD_UNDERCUT."""

from __future__ import annotations

from aris.field.rivals import RivalPitEstimate, RivalState, estimate_rival_pit_lap
from aris.field.standings import StandingRow
from aris.field.state import FieldState, ReplayIndex
from aris.recommend import (
    T2D_FALLBACK_NOTE,
    TRACK_POSITION_VALUE,
    _score_undercut_candidate,
    compute_field_undercut_value,
    compute_undercut_bonus,
    recommend,
)
from aris.simulate import ActionKind, simulate_undercut
from tests.test_circuit_deg import _zandvoort_state
from tests.test_strategy import _sample_state


def _row(**kwargs) -> StandingRow:
    defaults = dict(
        position=1,
        driver_id=1,
        code="VER",
        full_name="VER",
        team="RBR",
        lap_number=15,
        sector_idx=3,
        cumulative_time_s=1400.0,
        gap_to_leader_s=0.0,
        gap_ahead_s=None,
        gap_behind_s=1.5,
        last_lap_s=94.5,
        sector_1_s=30.0,
        sector_2_s=32.0,
        sector_3_s=32.5,
        compound="MEDIUM",
        tyre_life=22,
        pit_in=False,
        pit_out=False,
        track_status="1",
        stint_number=1,
    )
    defaults.update(kwargs)
    return StandingRow(**defaults)


def test_flag_off_uses_t2d_even_with_field(monkeypatch):
    monkeypatch.delenv("ARIS_FIELD_UNDERCUT", raising=False)
    state = _sample_state(gap_ahead_s=2.0, position=2)
    field = FieldState(
        session_id=1,
        index=ReplayIndex(15, 3),
        total_laps=57,
        standings=[
            _row(position=1, code="LEC", driver_id=2, gap_to_leader_s=0.0),
            _row(
                position=2,
                code="VER",
                driver_id=1,
                gap_to_leader_s=2.0,
                compound="SOFT",
                tyre_life=12,
            ),
        ],
    )
    result = recommend(state, top_k=3, mc_draws=0, field=field)
    pit = next(
        r
        for r in result.recommendations
        if r.action.kind != ActionKind.STAY_OUT or r.action.pit_laps
    )
    assert pit.narration_context.get("undercut_source") in {"t2d", "none"}
    assert "Field undercut" not in pit.evidence


def test_zandvoort_identity_with_flag_on_no_field(monkeypatch):
    monkeypatch.setenv("ARIS_FIELD_UNDERCUT", "1")
    result = recommend(_zandvoort_state(), top_k=3, mc_draws=0)
    labels = [r.label for r in result.recommendations]
    assert labels[0].startswith("Pit lap 33 for HARD")
    assert any(l.startswith("Pit lap 30 for HARD") for l in labels)
    assert any(
        r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps
        for r in result.recommendations
    )


def test_missing_ahead_estimate_falls_back_explicitly(monkeypatch):
    monkeypatch.setenv("ARIS_FIELD_UNDERCUT", "1")
    state = _sample_state(gap_ahead_s=2.5, position=2)
    bonus, source = compute_field_undercut_value(
        state, [], "HARD", 21.0, None, car_ahead_code="LEC"
    )
    assert source == "t2d_missing"
    assert bonus == compute_undercut_bonus(state)
    result = recommend(state, top_k=3, mc_draws=0, field=FieldState(
        session_id=1,
        index=ReplayIndex(15, 3),
        total_laps=57,
        standings=[_row(position=2, code="VER", compound="SOFT", tyre_life=12)],
    ))
    assert any(T2D_FALLBACK_NOTE in r.evidence for r in result.recommendations)


def test_simulate_undercut_never_returns_positive():
    state = _sample_state(lap_number=15, tyre_life=12, compound="SOFT", lag1_pace=94.5)
    rival = RivalPitEstimate(
        driver_code="LEC",
        compound="MEDIUM",
        tyre_life=4,
        estimated_pit_lap=28,
        laps_until_pit=13,
        confidence="MEDIUM",
        reasoning="test",
        last_lap_s=93.0,
        position=1,
    )
    delta = simulate_undercut(state, rival, "HARD", 21.0, None)
    assert delta <= 0.0


def test_field_path_when_rival_not_pitting_immediately(monkeypatch):
    monkeypatch.setenv("ARIS_FIELD_UNDERCUT", "1")
    state = _sample_state(
        gap_ahead_s=2.0,
        position=2,
        compound="SOFT",
        tyre_life=14,
        lag1_pace=95.0,
    )
    rs = RivalState(
        driver_code="LEC",
        position=1,
        compound="MEDIUM",
        tyre_life=18,
        gap_to_focus=2.0,
        gap_trend=0.0,
        team="Ferrari",
        last_lap_s=94.8,
    )
    est = estimate_rival_pit_lap(rs, 15, 57, "bahrain")
    assert est.estimated_pit_lap > 15 + 3
    bonus, source = compute_field_undercut_value(
        state, [est], "HARD", 21.0, None, car_ahead_code="LEC"
    )
    assert source in {"field", "t2d"}
    if source == "field":
        # T5 removed the −1.2 s cap; remaining-race delta is the signal.
        # Bound rejects the T7 double-sim bug (~−4000 s) without re-imposing the cap.
        assert bonus < 0
        assert bonus > -60.0


def test_score_undercut_comparable_windows_not_full_race_mismatch():
    """Remaining-race delta must be a few seconds, not a missing-lap (~90 s)
    or double-sim (~4000 s) artifact. Rival post-pit is a fresh set."""
    state = _sample_state(
        lap_number=31,
        tyre_life=31,
        compound="HARD",
        laps_remaining=26,
        total_laps=57,
        gap_ahead_s=2.0,
        lag1_pace=94.5,
    )
    rival = RivalPitEstimate(
        driver_code="LEC",
        compound="HARD",
        tyre_life=31,
        estimated_pit_lap=38,
        laps_until_pit=7,
        confidence="MEDIUM",
        reasoning="test",
        last_lap_s=94.5,
        position=1,
    )
    delta = _score_undercut_candidate(state, rival, "HARD", 21.8, None)
    assert abs(delta) < 60.0
    # T7 double-sim and T8 1-lap mismatch were ~90 s or thousands.
    assert abs(delta) < 90.0


def test_score_undercut_adds_track_position_when_ahead(monkeypatch):
    """When remaining-race time says we emerge ahead, add TRACK_POSITION_VALUE."""
    state = _sample_state(
        lap_number=31,
        tyre_life=31,
        compound="HARD",
        laps_remaining=26,
        total_laps=57,
        gap_ahead_s=2.0,
        lag1_pace=94.5,
    )
    rival = RivalPitEstimate(
        driver_code="LEC",
        compound="HARD",
        tyre_life=31,
        estimated_pit_lap=38,
        laps_until_pit=7,
        confidence="MEDIUM",
        reasoning="test",
        last_lap_s=94.5,
        position=1,
    )
    monkeypatch.setattr("aris.recommend.TRACK_POSITION_VALUE", 0.0)
    raw = _score_undercut_candidate(state, rival, "HARD", 21.8, None)
    monkeypatch.setattr("aris.recommend.TRACK_POSITION_VALUE", TRACK_POSITION_VALUE)
    scored = _score_undercut_candidate(state, rival, "HARD", 21.8, None)
    if raw > 0:
        assert abs(scored - (raw + TRACK_POSITION_VALUE)) < 1e-9
    else:
        assert abs(scored - raw) < 1e-9
    assert -60.0 < scored < 60.0
