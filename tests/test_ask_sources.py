"""H.2 — three retrieval sources exist and are non-empty real data."""

from aris.ask.sources import (
    load_concept_documents,
    load_decision_documents,
    load_race_documents,
)


def test_decision_source_is_real_jsonl():
    docs = load_decision_documents()
    # Aimed: the 14 fixture propose events, even if ARIS_ASK_DECISION_DIRS
    # is set to the live corpus in the shell (tests/conftest.py).
    assert len(docs) == 14, f"aimed 14 fixture decision docs, actual {len(docs)}"
    sai = [d for d in docs if d.facts.get("driver_code") == "SAI" and d.facts.get("lap") == 21]
    assert sai, "aimed a real SAI lap-21 propose from 2024_r15 JSONL, actual none"
    delta = sai[0].facts["delta_vs_stay_out_s"]
    # Aimed: exact JSONL value from 2024 Netherlands SAI L21 Pit now HARD.
    assert delta == -72.72805747985858, f"aimed -72.72805747985858, actual {delta}"
    assert sai[0].source == "decision"
    assert all(d.facts.get("true_compound_slopes") == "off" for d in docs)


def test_race_source_is_session_results_not_narrative():
    docs = load_race_documents()
    # Aimed: 958 classified rows dumped from local Postgres + 1 backtest summary.
    assert len(docs) >= 24, f"aimed >= 24 race docs, actual {len(docs)}"
    nl = [
        d
        for d in docs
        if d.facts.get("year") == 2024
        and d.facts.get("round_no") == 15
        and d.facts.get("driver_code") == "SAI"
    ]
    assert len(nl) == 1, f"aimed 1 SAI 2024 R15 result, actual {len(nl)}"
    assert nl[0].facts["finish_pos"] == 5, f"aimed finish_pos=5, actual {nl[0].facts['finish_pos']}"
    assert nl[0].facts["grid_pos"] == 10, f"aimed grid_pos=10, actual {nl[0].facts['grid_pos']}"
    assert nl[0].facts["pit_in_count"] == 1, f"aimed pit_in_count=1, actual {nl[0].facts['pit_in_count']}"
    assert "narrative" not in nl[0].text.lower() or "not a race narrative" in nl[0].text.lower()


def test_concept_source_is_small_and_cited():
    docs = load_concept_documents()
    # Aimed: a small cited set (not thousands). Actual count below.
    assert 8 <= len(docs) <= 40, f"aimed 8-40 concept docs, actual {len(docs)}"
    ids = {d.facts["concept_id"] for d in docs}
    for needed in ("undercut", "overcut", "safety-car-deployment", "virtual-safety-car", "pit-lane-speed-and-layout"):
        assert needed in ids, f"aimed concept {needed} present, actual missing"
    sc = next(d for d in docs if d.facts["concept_id"] == "safety-car-deployment")
    assert "55.3" in sc.citation or "55.3" in sc.facts["source"]
    assert "fia.com" in sc.facts["url"]
