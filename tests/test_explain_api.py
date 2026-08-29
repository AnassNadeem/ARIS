"""T12 — /api/explain/* handlers return schema-valid JSON."""

from __future__ import annotations

from aris.explain.ghost import clear_ghost_vs_real_cache
from aris.explain.session import set_bundle_override
from aris.schemas import DegradationCurveResponse, GhostVsRealResponse, RaceDebriefResponse
from tests.fixtures.explain_zandvoort import zandvoort_2025_bundle


def setup_function() -> None:
    clear_ghost_vs_real_cache()
    set_bundle_override(zandvoort_2025_bundle())


def teardown_function() -> None:
    set_bundle_override(None)
    clear_ghost_vs_real_cache()


def test_explain_routes_registered():
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/explain/degradation" in paths
    assert "/api/explain/ghost" in paths
    assert "/api/explain/debrief" in paths


def test_degradation_endpoint_json():
    from backend.aris_api import explain_degradation

    payload = explain_degradation("2025-15-R", "VER", 1)
    body = DegradationCurveResponse.model_validate(payload)
    assert body.tyre_age
    assert len(body.tyre_age) == len(body.predicted_deg_s) == len(body.actual_deg_s)
    assert body.driver == "VER"


def test_ghost_endpoint_json():
    from backend.aris_api import explain_ghost

    payload = explain_ghost("2025-15-R", "VER")
    body = GhostVsRealResponse.model_validate(payload)
    assert body.ghost.laps
    assert body.real.laps
    assert len(body.ghost.laps) == len(body.ghost.position)
    assert body.ghost.laps == body.real.laps
    assert len(body.delta.gap_delta) == len(body.delta.laps)


def test_debrief_endpoint_json():
    from backend.aris_api import explain_debrief

    payload = explain_debrief("2025-15-R", "VER")
    body = RaceDebriefResponse.model_validate(payload)
    assert body.timeline.pit_stops
    assert body.decisions
    assert body.decisions[0].recommend_top3
