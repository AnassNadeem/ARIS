"""T12 — race debrief timeline and recommend() decisions."""

from __future__ import annotations

from aris.explain.debrief import get_race_debrief
from aris.explain.session import set_bundle_override
from tests.fixtures.explain_zandvoort import zandvoort_2025_bundle


def setup_function() -> None:
    set_bundle_override(zandvoort_2025_bundle())


def teardown_function() -> None:
    set_bundle_override(None)


def test_zandvoort_debrief_timeline_and_decisions():
    result = get_race_debrief("2025-15-R", "VER")
    timeline = result["timeline"]
    decisions = result["decisions"]
    meta = result["metadata"]
    assert timeline["pit_stops"], "expected pit stops on the timeline"
    assert timeline["sc_vsc_periods"], "expected SC/VSC periods"
    assert timeline["rain_periods"], "expected rain periods from weather Rainfall"
    assert decisions, "expected at least one key decision"
    top = decisions[0]["recommend_top3"]
    assert top, "recommend() top-3 missing"
    assert len(top) <= 3
    assert decisions[0]["explanation"]
    assert decisions[0]["chosen_action"]
    assert meta["circuit"] == "Netherlands"
    assert meta["season"] == 2025
    assert meta["total_laps"] >= 1
