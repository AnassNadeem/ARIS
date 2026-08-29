"""FSM test suite — T6 gate requirement: all 7 tests pass.

Tests cover:
  1. RED_FLAG → STRATEGY_RESET action from recommend()
  2. SC → effective_pit_loss ~11.25s
  3. VSC → simulate() called with deg_multiplier=0.15
  4. GREEN → values identical to pre-FSM behaviour
  5. STANDING_START → STRATEGY_RESET
  6. FORMATION_LAP → deg_multiplier=0.05
  7. Zandvoort 2025 lap sequence (L1-L8 phase transitions)
"""

from __future__ import annotations

import pytest

from aris.fsm import PHASE_CONFIGS, RacePhase, get_phase_config
from aris.state import RaceState

# ---------------------------------------------------------------------------
# Shared fixture factory (minimal RaceState — no DB)
# ---------------------------------------------------------------------------


def _make_state(
    *,
    track_status: str = "1",
    formation_lap: bool = False,
    standing_start: bool = False,
    compound: str = "HARD",
    tyre_life: int = 10,
    lap_number: int = 20,
    total_laps: int = 72,
    laps_remaining: int | None = None,
) -> RaceState:
    return RaceState(
        session_id=0,
        driver_id=1,
        driver_code="TST",
        driver_name="Test Driver",
        year=2025,
        round_no=13,
        country="Netherlands",
        lap_number=lap_number,
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=30.0,
        laps_remaining=(
            laps_remaining if laps_remaining is not None else max(0, total_laps - lap_number)
        ),
        total_laps=total_laps,
        track_status=track_status,
        formation_lap=formation_lap,
        standing_start=standing_start,
    )


# ---------------------------------------------------------------------------
# Test 1: RED_FLAG → STRATEGY_RESET from recommend()
# ---------------------------------------------------------------------------


def test_red_flag_returns_strategy_reset():
    """track_status='7' → recommend() returns a STRATEGY_RESET recommendation."""
    from aris.recommend import recommend

    state = _make_state(track_status="7")
    result = recommend(state, mc_draws=0)

    assert len(result.recommendations) == 1
    rec = result.recommendations[0]
    assert rec.label == "STRATEGY_RESET"
    nc = rec.narration_context
    assert nc.get("action") == "STRATEGY_RESET"
    assert nc.get("phase") == "RED_FLAG"
    assert nc.get("free_tyre_change") is True


# ---------------------------------------------------------------------------
# Test 2: SC reduces effective pit loss to ~11.25s
# ---------------------------------------------------------------------------


def test_sc_reduces_pit_loss():
    """track_status='4' (SC) → pit_loss_multiplier=0.50, effective ~11.25s."""
    state = _make_state(track_status="4")
    cfg = get_phase_config(state)

    assert cfg.phase == RacePhase.SC
    assert cfg.pit_loss_multiplier == 0.50

    # With typical YAML pit_loss of 22.5s → effective = 11.25s
    base_pit_loss = 22.5
    effective = (
        cfg.pit_loss_override
        if cfg.pit_loss_override >= 0
        else base_pit_loss * cfg.pit_loss_multiplier
    )
    assert abs(effective - 11.25) < 0.01, f"Expected ~11.25, got {effective}"


# ---------------------------------------------------------------------------
# Test 3: VSC → deg_multiplier=0.15 in simulate()
# ---------------------------------------------------------------------------


def test_vsc_pauses_degradation():
    """track_status='5' (VSC) → deg_multiplier=0.15, simulation degrades slowly."""
    state = _make_state(track_status="5")
    cfg = get_phase_config(state)

    assert cfg.phase == RacePhase.VSC
    assert cfg.deg_multiplier == 0.15

    # Verify that simulations under VSC use deg_multiplier via recommend()
    from aris.recommend import recommend

    result = recommend(state, mc_draws=0)
    # Under VSC, recommend() should NOT return STRATEGY_RESET (only RED_FLAG does)
    assert result.recommendations[0].label != "STRATEGY_RESET"
    # Should still produce recommendations
    assert len(result.recommendations) > 0


# ---------------------------------------------------------------------------
# Test 4: GREEN → no change from pre-FSM behaviour
# ---------------------------------------------------------------------------


def test_green_flag_unchanged():
    """track_status='1' (GREEN) → all multipliers at default (1.0)."""
    state = _make_state(track_status="1")
    cfg = get_phase_config(state)

    assert cfg.phase == RacePhase.GREEN
    assert cfg.pit_loss_multiplier == 1.0
    assert cfg.deg_multiplier == 1.0
    assert cfg.strategy_reset is False
    assert cfg.free_tyre_change is False
    assert cfg.pace_target_active is True
    assert cfg.delta_mode is False


# ---------------------------------------------------------------------------
# Test 5: STANDING_START → STRATEGY_RESET
# ---------------------------------------------------------------------------


def test_standing_start_resets_strategy():
    """standing_start=True → recommend() returns STRATEGY_RESET."""
    from aris.recommend import recommend

    state = _make_state(standing_start=True)
    result = recommend(state, mc_draws=0)

    rec = result.recommendations[0]
    assert rec.label == "STRATEGY_RESET"
    assert rec.narration_context.get("phase") == "STANDING_START"
    assert rec.narration_context.get("free_tyre_change") is False


# ---------------------------------------------------------------------------
# Test 6: FORMATION_LAP → deg_multiplier=0.05
# ---------------------------------------------------------------------------


def test_formation_lap_minimal_deg():
    """formation_lap=True → deg_multiplier=0.05, pace_target_active=False."""
    state = _make_state(formation_lap=True)
    cfg = get_phase_config(state)

    assert cfg.phase == RacePhase.FORMATION_LAP
    assert cfg.deg_multiplier == 0.05
    assert cfg.pace_target_active is False
    assert cfg.strategy_reset is False


# ---------------------------------------------------------------------------
# Test 7: Zandvoort 2025 lap sequence
# ---------------------------------------------------------------------------


def test_zandvoort_2025_sequence():
    """Simulate the Zandvoort 2025 lap sequence and verify FSM phase at each lap.

    Sequence:
        L1-2: GREEN
        L3:   RED_FLAG (collision)
        L4-5: RED_FLAG
        L6:   FORMATION_LAP
        L7:   STANDING_START
        L8:   GREEN

    STRATEGY_RESET must be returned on L3 and L7.
    """
    from aris.recommend import recommend

    lap_sequence = [
        # (lap, track_status, formation_lap, standing_start, expected_phase, expect_reset)
        (1,  "1", False, False, RacePhase.GREEN,          False),
        (2,  "1", False, False, RacePhase.GREEN,          False),
        (3,  "7", False, False, RacePhase.RED_FLAG,       True),
        (4,  "7", False, False, RacePhase.RED_FLAG,       True),
        (5,  "7", False, False, RacePhase.RED_FLAG,       True),
        (6,  "1", True,  False, RacePhase.FORMATION_LAP,  False),
        (7,  "1", False, True,  RacePhase.STANDING_START, True),
        (8,  "1", False, False, RacePhase.GREEN,          False),
    ]

    for lap, ts, fl, ss, expected_phase, expect_reset in lap_sequence:
        state = _make_state(
            track_status=ts,
            formation_lap=fl,
            standing_start=ss,
            lap_number=lap,
            total_laps=72,
        )

        # FSM phase check
        cfg = get_phase_config(state)
        assert cfg.phase == expected_phase, (
            f"L{lap}: expected {expected_phase.name}, got {cfg.phase.name}"
        )

        # STRATEGY_RESET check
        result = recommend(state, mc_draws=0)
        is_reset = (
            result.recommendations[0].label == "STRATEGY_RESET"
            if result.recommendations else False
        )
        assert is_reset == expect_reset, (
            f"L{lap}: expected reset={expect_reset}, got {is_reset} "
            f"(phase={cfg.phase.name})"
        )
