"""T10-D — vectorised remaining-race Monte Carlo."""

from __future__ import annotations

import time

from aris.simulate_mc import compare_actions_mc, sample_remaining_race

_BASE = dict(
    n_scenarios=200,
    laps_remaining=50,
    base_lap_time_s=90.0,
    deg_sigma=0.15,
    pit_compound_slope=0.03,
    pit_loss_s=20.0,
    warmup_penalty_s=0.8,
    p_sc_per_lap=0.02,
    sc_duration_laps=3,
    sc_pit_loss_multiplier=0.50,
)


def test_stay_out_faster_than_pit_on_fresh_tyres():
    """A car on fresh tyres should prefer staying out over immediate pit."""
    stay = sample_remaining_race(
        **_BASE, deg_slope=0.03, tyre_age_start=2, pit_lap=None, seed=0
    )
    pit = sample_remaining_race(
        **_BASE, deg_slope=0.03, tyre_age_start=2, pit_lap=0, seed=0
    )
    assert float(stay.mean()) < float(pit.mean())


def test_pit_faster_than_stay_on_old_tyres():
    """A car on very old tyres (age=35, HARD) should prefer pitting."""
    old = {**_BASE, "deg_slope": 0.08, "tyre_age_start": 35, "pit_compound_slope": 0.03}
    stay = sample_remaining_race(**old, pit_lap=None, seed=1)
    pit = sample_remaining_race(**old, pit_lap=0, seed=1)
    assert float(pit.mean()) < float(stay.mean())


def test_higher_sc_risk_increases_pit_attractiveness():
    """Doubling p_sc_per_lap should not decrease the benefit of pitting under SC."""
    actions = [
        {
            "name": "stay",
            "pit_lap": None,
            "compound": "HARD",
            "pit_compound_slope": 0.03,
            "pit_loss": 0.0,
        },
        {
            "name": "pit",
            "pit_lap": 0,
            "compound": "HARD",
            "pit_compound_slope": 0.03,
            "pit_loss": 20.0,
        },
    ]
    base = {
        "laps_remaining": 40,
        "base_lap_time": 90.0,
        "deg_slope": 0.05,
        "deg_sigma": 0.10,
        "tyre_age": 18,
        "p_sc_per_lap": 0.05,
    }

    def _benefit(p_sc: float) -> float:
        rows = compare_actions_mc(
            actions,
            {**base, "p_sc_per_lap": p_sc},
            n_scenarios=400,
            warmup_penalties={"HARD": 0.8},
            seed=7,
        )
        by_name = {r["action"]: r for r in rows}
        return by_name["stay"]["expected_total_s"] - by_name["pit"]["expected_total_s"]

    assert _benefit(0.10) >= _benefit(0.05) - 1e-9


def test_vectorised_speed():
    """200 scenarios × 50 laps must complete in < 2 seconds."""
    start = time.perf_counter()
    sample_remaining_race(
        n_scenarios=200,
        laps_remaining=50,
        base_lap_time_s=90.0,
        deg_slope=0.05,
        deg_sigma=0.2,
        tyre_age_start=10,
        pit_lap=8,
        pit_compound_slope=0.03,
        pit_loss_s=20.0,
        warmup_penalty_s=0.8,
        p_sc_per_lap=0.03,
        seed=0,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"MC too slow: {elapsed:.2f}s"


def test_p_best_sums_to_one():
    """p_best across all actions should sum to approximately 1.0."""
    actions = [
        {
            "name": "stay",
            "pit_lap": None,
            "compound": "HARD",
            "pit_compound_slope": 0.03,
            "pit_loss": 0.0,
        },
        {
            "name": "pit_now",
            "pit_lap": 0,
            "compound": "MEDIUM",
            "pit_compound_slope": 0.05,
            "pit_loss": 20.0,
        },
        {
            "name": "pit_8",
            "pit_lap": 8,
            "compound": "HARD",
            "pit_compound_slope": 0.03,
            "pit_loss": 20.0,
        },
    ]
    base = {
        "laps_remaining": 40,
        "base_lap_time": 90.0,
        "deg_slope": 0.05,
        "deg_sigma": 0.15,
        "tyre_age": 12,
        "p_sc_per_lap": 0.03,
    }
    rows = compare_actions_mc(actions, base, n_scenarios=200, seed=3)
    total = sum(r["p_best"] for r in rows)
    assert abs(total - 1.0) < 0.01
