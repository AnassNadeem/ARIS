"""T12 — ARIS ghost vs real classified run."""

from __future__ import annotations

import pytest

from aris.explain.ghost import clear_ghost_vs_real_cache, get_ghost_lap_ticks, get_ghost_vs_real
from aris.explain.session import set_bundle_override
from tests.fixtures.explain_zandvoort import zandvoort_2025_bundle


def setup_function() -> None:
    clear_ghost_vs_real_cache()
    set_bundle_override(zandvoort_2025_bundle())


def teardown_function() -> None:
    set_bundle_override(None)
    clear_ghost_vs_real_cache()


def test_zandvoort_ver_ghost_and_real_aligned():
    result = get_ghost_vs_real("VER", "2025-15-R")
    ghost = result["ghost"]
    real = result["real"]
    delta = result["delta"]
    assert ghost["laps"], "expected non-empty ghost laps"
    assert real["laps"], "expected non-empty real laps"
    n = min(len(ghost["laps"]), len(real["laps"]))
    assert n >= 8
    assert len(ghost["position"]) == len(ghost["laps"])
    assert len(real["position"]) == len(real["laps"])
    assert len(ghost["gap_to_leader"]) == len(ghost["laps"])
    assert len(real["gap_to_leader"]) == len(real["laps"])
    assert ghost["laps"][:n] == real["laps"][:n]
    assert delta["laps"][:n] == ghost["laps"][:n]
    assert len(delta["position_delta"]) == len(delta["laps"])
    assert len(delta["gap_delta"]) == len(delta["laps"])
    assert real["pit_laps"]
    assert ghost["compound"]
    assert real["compound"]
    assert ghost["laps"][0] == 1


def test_zandvoort_ver_ghost_from_lap_one():
    result = get_ghost_vs_real("VER", "2025-15-R")
    ticks = result["ticks"]
    plan = result["plan"]
    assert ticks.get(1) is not None
    assert ticks[1].get("from_lap_one") is True
    assert plan["decision_lap"] in (1, 2)
    assert plan["start_compound"] in ("SOFT", "MEDIUM", "HARD")
    last = max(int(k) for k in ticks)
    assert ticks.get(last) is not None
    print(
        "GHOST PLAN",
        plan,
        "delta L1",
        ticks[1]["ghost_cumulative_delta"],
        "delta end",
        ticks[last]["ghost_cumulative_delta"],
    )
    keyed = get_ghost_lap_ticks("VER", "2025-15-R")
    assert keyed.get(1) is not None
    assert keyed[1]["ghost_cumulative_delta"] == ticks[1]["ghost_cumulative_delta"]


def test_zandvoort_ver_ghost_tower_matches_sim_rank_not_grid():
    """Tower rank is ARIS cumulative simulation; real car stays P1 on the classified run."""
    result = get_ghost_vs_real("VER", "2025-15-R")
    assert result["real"]["position"][0] == 1
    ticks = result["ticks"]
    assert ticks.get(1) is not None
    assert ticks[1]["ghost_position"] == result["ghost"]["position"][0]


def test_ghost_and_real_pit_counts_match_sample_races():
    from tests.fixtures.explain_zandvoort import DRIVERS

    failures: list[str] = []
    for code in DRIVERS:
        result = get_ghost_vs_real(code, "2025-15-R")
        real_n = len(result["real"]["pit_laps"])
        ghost_n = len(result["ghost"]["pit_laps"])
        if real_n != ghost_n:
            failures.append(
                f"{code}: real {result['real']['pit_laps']} ghost {result['ghost']['pit_laps']}"
            )
    assert not failures, "\n".join(failures)


def test_ver_zandvoort_ghost_position_anchored_to_real_and_delta():
    """Tower position is anchored to VER's real classified state, offset only
    by the model's ``ghost_cumulative_delta`` — never a raw independent
    model cumulative time, and never unconditionally mirroring the real car.

    - Lap 1 (delta == 0, ARIS has not diverged yet): the ghost is deployed
      from lap 1 sitting exactly on VER's own real classified position —
      this is required regardless of whether ARIS's plan matches what the
      driver actually did.
    - Lap 10 (delta far from 0 — ARIS's plan has diverged): the ghost's
      position must move away from VER's real position, proving the ghost
      reacts to the model's delta rather than always mirroring the real car.
    """
    result = get_ghost_vs_real("VER", "2025-15-R")
    ticks = result["ticks"]
    assert ticks.get(1) is not None
    assert ticks.get(10) is not None

    idx1 = result["ghost"]["laps"].index(1)
    assert ticks[1]["ghost_cumulative_delta"] == pytest.approx(0.0, abs=1e-6)
    assert ticks[1]["ghost_position"] == result["ghost"]["position"][idx1]
    assert ticks[1]["ghost_position"] == result["real"]["position"][idx1]
    assert abs(
        float(ticks[1]["gap_to_leader_s"]) - float(result["real"]["gap_to_leader"][idx1])
    ) < 0.05

    idx10 = result["ghost"]["laps"].index(10)
    assert ticks[10]["ghost_cumulative_delta"] != pytest.approx(0.0, abs=1e-6)
    assert ticks[10]["ghost_position"] == result["ghost"]["position"][idx10]
    assert ticks[10]["ghost_position"] != result["real"]["position"][idx10]
