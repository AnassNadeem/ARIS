"""H2.3 — Ask retrieval prefers G1.5-shipped proposes over overlay duplicates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aris.ask.grounded import answer_question
from aris.ask.retrieve import AskIndex
from aris.ask.sources import (
    decision_to_document,
    json_number,
    load_decision_documents,
    model_config_for_record,
)
from aris.physics.compounds import TRUE_COMPOUND_SLOPES_ENV

_SHIPPED_DELTA = -72.72805747985858
_OVERLAY_DELTA = -24.164300000000186


def _propose(
    *,
    event_id: str,
    delta: float,
    label: str,
    mode: str | None,
    ts: str,
) -> dict:
    rec: dict = {
        "event_id": event_id,
        "event": "propose",
        "ts": ts,
        "source": "backtest",
        "session_id": 15,
        "driver_id": 15,
        "driver_code": "SAI",
        "year": 2024,
        "round_no": 15,
        "country": "Netherlands",
        "kind": "pit",
        "lap": 21,
        "recommendation": {
            "rank": 1,
            "label": label,
            "action": {
                "kind": "pit_now",
                "pit_lap": None,
                "pit_compound": "HARD",
                "pit_laps": None,
                "pit_compounds": None,
                "corner_index": None,
                "distance_m": None,
            },
            "delta_vs_stay_out_s": delta,
            "mean_race_time_s": 3992.544223727452,
            "confidence_std_s": 0.0,
        },
    }
    if mode is not None:
        rec["true_compound_slopes"] = mode
    return rec


def test_model_config_uses_tag_not_timestamp_when_present():
    rec = _propose(
        event_id="tagged-overlay",
        delta=_OVERLAY_DELTA,
        label="Pit lap 29 for HARD",
        mode="unconstrained",
        ts="2026-08-13T14:36:46.375032+00:00",  # g1-window time, overlay tag
    )
    assert model_config_for_record(rec) == "unconstrained"


def test_untagged_overlay_window_is_not_treated_as_shipped():
    rec = _propose(
        event_id="untagged-g2",
        delta=_OVERLAY_DELTA,
        label="Pit lap 29 for HARD",
        mode=None,
        ts="2026-08-13T21:39:16.159545+00:00",
    )
    assert model_config_for_record(rec) == "unknown-overlay"


def test_load_drops_overlay_duplicate_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "mixed.jsonl"
    shipped = _propose(
        event_id="shipped",
        delta=_SHIPPED_DELTA,
        label="Pit now for HARD",
        mode="off",
        ts="2026-08-13T14:36:46.375032+00:00",
    )
    overlay = _propose(
        event_id="overlay",
        delta=_OVERLAY_DELTA,
        label="Pit lap 29 for HARD",
        mode="unconstrained",
        ts="2026-08-13T21:39:16.159545+00:00",
    )
    path.write_text(
        json.dumps(overlay) + "\n" + json.dumps(shipped) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ARIS_ASK_DECISION_DIRS", str(path))
    monkeypatch.delenv("ARIS_ASK_INCLUDE_OVERLAY_DECISIONS", raising=False)

    docs = load_decision_documents()
    assert len(docs) == 1, f"aimed 1 shipped doc, actual {len(docs)}"
    assert docs[0].facts["delta_vs_stay_out_s"] == _SHIPPED_DELTA
    assert docs[0].facts["true_compound_slopes"] == "off"

    both = load_decision_documents(include_overlay=True)
    assert {d.facts["event_id"] for d in both} == {"shipped", "overlay"}


def test_grounding_returns_shipped_not_overlay_duplicate():
    """Two conflicting SAI NL L21 records; answer must be the G1.5 copy."""
    overlay = decision_to_document(
        _propose(
            event_id="overlay-first",
            delta=_OVERLAY_DELTA,
            label="Pit lap 29 for HARD",
            mode="unconstrained",
            ts="2026-08-13T21:39:16.159545+00:00",
        )
    )
    shipped = decision_to_document(
        _propose(
            event_id="shipped-second",
            delta=_SHIPPED_DELTA,
            label="Pit now for HARD",
            mode="off",
            ts="2026-08-13T14:36:46.375032+00:00",
        )
    )
    # Overlay is first in the index so naive ranking can surface it.
    index = AskIndex.from_documents([overlay, shipped])
    answer = answer_question(
        None,
        "What did ARIS recommend for SAI at the 2024 Netherlands race on lap 21?",
        index=index,
    )
    assert json_number(_SHIPPED_DELTA) in answer, f"aimed shipped delta, actual {answer[:300]!r}"
    assert json_number(_OVERLAY_DELTA) not in answer
    assert "Pit now for HARD" in answer
    assert "shipped-second" in answer


def test_persist_tags_active_overlay_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from aris.decisions.persist import JsonlDecisionLog
    from aris.decisions.queue import DecisionKind, DecisionQueue
    from aris.state import RaceState

    monkeypatch.setenv(TRUE_COMPOUND_SLOPES_ENV, "isotonic")
    path = tmp_path / "events.jsonl"
    q = DecisionQueue()
    q.bind_log(JsonlDecisionLog(path, source="test"))
    q.propose(
        RaceState(
            session_id=1,
            driver_id=1,
            driver_code="HAM",
            driver_name="Lewis",
            year=2025,
            round_no=1,
            country="Bahrain",
            lap_number=10,
            compound="MEDIUM",
            tyre_life=10,
            fuel_kg=80.0,
            laps_remaining=47,
            lag1_pace=95.0,
            lag2_pace=95.1,
            stint_roll3=95.0,
        ),
        kind=DecisionKind.PIT,
        use_llm=False,
        mc_draws=0,
    )
    rec = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["true_compound_slopes"] == "isotonic"
