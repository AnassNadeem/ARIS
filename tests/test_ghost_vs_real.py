"""T12 — ARIS ghost vs real classified run."""

from __future__ import annotations

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


def test_zandvoort_ver_ghost_starts_at_grid_position():
    result = get_ghost_vs_real("VER", "2025-15-R")
    assert result["real"]["position"][0] == 1
    assert result["ghost"]["position"][0] == 1
    assert result["ticks"][1]["ghost_position"] == 1


def test_ghost_and_real_pit_counts_match_sample_races():
    from tests.fixtures.explain_zandvoort import DRIVERS

    failures: list[str] = []
    for code in DRIVERS:
        result = get_ghost_vs_real(code, "2025-15-R")
        real_n = len(result["real"]["pit_laps"])
        ghost_n = len(result["ghost"]["pit_laps"])
        if real_n != ghost_n:
            failures.append(f"{code}: real {result['real']['pit_laps']} ghost {result['ghost']['pit_laps']}")
    assert not failures, "\n".join(failures)
