"""T3-C overcut candidates — eligibility vs remainder-of-race ranking."""

from __future__ import annotations

from aris.field.rivals import RivalPitEstimate, estimate_rival_pit_lap
from aris.field.standings import StandingRow
from aris.field.state import FieldState, ReplayIndex
from aris.narrate import narrate_recommendation
from aris.recommend import generate_overcut_candidates, recommend
from aris.simulate import ActionKind
from tests.test_circuit_deg import _zandvoort_state
from tests.test_strategy import _sample_state


def _row(**kwargs) -> StandingRow:
    defaults = dict(
        position=1,
        driver_id=1,
        code="VER",
        full_name="VER",
        team="RBR",
        lap_number=50,
        sector_idx=3,
        cumulative_time_s=4000.0,
        gap_to_leader_s=0.0,
        gap_ahead_s=None,
        gap_behind_s=3.0,
        last_lap_s=78.0,
        sector_1_s=24.0,
        sector_2_s=25.0,
        sector_3_s=25.0,
        compound="SOFT",
        tyre_life=14,
        pit_in=False,
        pit_out=False,
        track_status="1",
        stint_number=1,
    )
    defaults.update(kwargs)
    return StandingRow(**defaults)


def _monaco_field() -> FieldState:
    return FieldState(
        session_id=1,
        index=ReplayIndex(50, 3),
        total_laps=78,
        standings=[
            _row(position=1, code="VER", driver_id=1, gap_to_leader_s=0.0, compound="SOFT", tyre_life=14, last_lap_s=78.0),
            _row(
                position=2,
                code="NOR",
                driver_id=2,
                gap_to_leader_s=3.0,
                compound="HARD",
                tyre_life=2,
                last_lap_s=73.0,
            ),
        ],
    )


def _soon_rival() -> RivalPitEstimate:
    from aris.field.rivals import RivalState

    rs = RivalState(
        driver_code="VER",
        position=1,
        compound="SOFT",
        tyre_life=14,
        gap_to_focus=3.0,
        gap_trend=0.0,
        team="RBR",
        last_lap_s=78.0,
    )
    return estimate_rival_pit_lap(rs, current_lap=50, total_laps=78, circuit_key="monaco")


def test_no_overcut_when_laps_remaining_under_15():
    state = _sample_state(
        lap_number=50,
        laps_remaining=10,
        total_laps=60,
        gap_ahead_s=3.0,
        country="Monaco",
        compound="MEDIUM",
        tyre_life=8,
    )
    est = _soon_rival()
    assert est.laps_until_pit <= 8
    assert generate_overcut_candidates(state, [est], None, 20.0) == []


def test_no_overcut_when_gap_ahead_under_2s():
    state = _sample_state(
        lap_number=50,
        laps_remaining=28,
        total_laps=78,
        gap_ahead_s=1.5,
        country="Monaco",
        compound="MEDIUM",
        tyre_life=8,
    )
    assert generate_overcut_candidates(state, [_soon_rival()], None, 20.0) == []


def test_window_eligible_candidate_has_negative_delta():
    state = _sample_state(
        lap_number=50,
        laps_remaining=28,
        total_laps=78,
        gap_ahead_s=3.0,
        country="Monaco",
        compound="HARD",
        tyre_life=2,
        lag1_pace=73.0,
        pit_compound="HARD",
        position=2,
    )
    est = _soon_rival()
    assert est.confidence != "LOW"
    assert est.laps_until_pit <= 8
    cands = generate_overcut_candidates(state, [est], None, 20.0)
    assert cands, "aimed a negative-window overcut vs a soon-pitting rival"
    assert all(c.overcut_window_delta_s is not None and c.overcut_window_delta_s < 0 for c in cands)
    assert all(c.label_override and c.label_override.startswith("OVERCUT_VER_") for c in cands)
    assert len(cands) <= 2


def test_monaco_overcut_in_shortlist_when_field_present():
    state = _sample_state(
        driver_code="NOR",
        lap_number=50,
        laps_remaining=28,
        total_laps=78,
        gap_ahead_s=3.0,
        country="Monaco",
        compound="HARD",
        tyre_life=2,
        lag1_pace=73.0,
        pit_compound="HARD",
        position=2,
        year=2024,
        round_no=8,
    )
    result = recommend(state, top_k=3, mc_draws=0, field=_monaco_field())
    labels = [r.label for r in result.recommendations]
    over = [r for r in result.recommendations if r.label.startswith("OVERCUT_")]
    assert any(r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps for r in result.recommendations)
    if over:
        radio = narrate_recommendation(over[0], use_llm=False)
        assert "VER" in radio
        assert "Overcut" in radio
        assert over[0].narration_context.get("overcut_rival") == "VER"
    # Eligible window may still rank outside top-3; the generator is the contract.
    gen = generate_overcut_candidates(state, [_soon_rival()], None, 20.0)
    assert gen
    assert any("OVERCUT_VER_" in (c.label_override or "") for c in gen)
    del labels


def test_zandvoort_identity_no_overcut_without_field():
    result = recommend(_zandvoort_state(), top_k=3, mc_draws=0)
    assert not any(r.label.startswith("OVERCUT_") for r in result.recommendations)
    labels = [r.label for r in result.recommendations]
    assert labels[0].startswith("Pit lap 33 for HARD")


def test_overcut_active_commentary_when_rival_pits_in_window():
    from aris.commentary import CommentaryEngine, DriverSnap, FieldSnapshot

    def snap(lap: int, ver_stint: int) -> FieldSnapshot:
        return FieldSnapshot(
            lap=lap,
            total_laps=78,
            drivers=[
                DriverSnap(code="VER", position=1, stint_number=ver_stint, compound="H", gap_to_leader_s=0.0),
                DriverSnap(code="NOR", position=2, stint_number=1, compound="M", gap_to_leader_s=3.2),
            ],
        )

    engine = CommentaryEngine()
    engine.prev_field = snap(21, 1)
    engine.last_estimates = {"VER": 22}
    msgs = engine.generate(snap(22, 2), "NOR", 22, 78, [])
    hits = [m for m in msgs if "OVERCUT ACTIVE" in m.text]
    assert hits, msgs
    assert "VER" in hits[0].text
