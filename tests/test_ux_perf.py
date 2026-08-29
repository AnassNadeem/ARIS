"""UX / perf helpers: sector paths, DNF/DNS, SSE gather, quick-analysis route."""

from __future__ import annotations

import inspect

from backend.live import _annotate_timing_status, _inactive_from_laps
from backend.models import CircuitMarker, LiveTimingRow
from backend.sessions import ensure_sector_paths, sector_paths_from_outline


def test_sector_paths_split_into_three():
    xs = [float(i) for i in range(12)]
    ys = [0.0] * 12
    markers = [
        CircuitMarker(kind="s1", x=3.0, y=0.0, label="S1"),
        CircuitMarker(kind="s2", x=7.0, y=0.0, label="S2"),
        CircuitMarker(kind="s3", x=11.0, y=0.0, label="S3"),
    ]
    paths = sector_paths_from_outline(xs, ys, markers)
    assert [p.kind for p in paths] == ["s1", "s2", "s3"]
    assert paths[0].x[0] == 0.0
    assert paths[2].x[-1] == 0.0  # closed back to S/F


def test_sector_paths_fallback_without_markers():
    xs = [float(i) for i in range(9)]
    ys = [1.0] * 9
    paths = sector_paths_from_outline(xs, ys, [])
    assert len(paths) == 3
    assert all(p.x and p.y for p in paths)


def test_ensure_sector_paths_fills_empty():
    from backend.models import CircuitMapResponse

    cmap = CircuitMapResponse(year=2025, round_number=15, x=[0, 1, 2, 3, 4, 5], y=[0, 0, 0, 0, 0, 0], available=True)
    filled = ensure_sector_paths(cmap)
    assert len(filled.sector_paths) == 3


def test_inactive_dns_and_dnf():
    codes = {1: "VER", 44: "HAM", 16: "LEC"}
    laps = [
        {"driver_number": 1, "lap_number": 20},
        {"driver_number": 44, "lap_number": 12},
        {"driver_number": 16, "lap_number": 1},
    ]
    out = _inactive_from_laps(laps, codes, total_laps=57)
    assert "LEC" in out
    assert "HAM" in out
    assert "VER" not in out


def test_annotate_timing_dns_dnf():
    rows = [
        LiveTimingRow(position=1, driver_code="VER", lap_number=20, last_lap_ms=72000, best_lap_ms=71000),
        LiveTimingRow(position=2, driver_code="ALB", lap_number=0, eliminated=True, reason="DID NOT START"),
        LiveTimingRow(position=3, driver_code="GAS", lap_number=8, eliminated=True, reason="RETIRED"),
    ]
    out = _annotate_timing_status(rows, field_lap=20)
    by = {r.driver_code: r for r in out}
    assert by["VER"].status == "RUNNING"
    assert by["ALB"].status == "DNS"
    assert by["GAS"].status == "DNF"
    assert by["VER"].laps_completed == 20
    assert by["GAS"].laps_down == 12


def test_laps_upto_skips_undated_rows():
    from datetime import datetime, timezone

    from backend.live import _laps_upto

    clock = datetime(2025, 8, 31, 13, 0, tzinfo=timezone.utc)
    rows = [
        {"lap_number": 1, "date_start": "2025-08-31T13:00:00Z"},
        {"lap_number": 23, "date_start": None},
        {"lap_number": 24},
        {"lap_number": 2, "date_start": "2025-08-31T13:02:00Z"},
    ]
    out = _laps_upto(rows, clock)
    assert [r["lap_number"] for r in out] == [1]


def test_current_race_lap_starts_at_one():
    from datetime import datetime, timedelta, timezone

    from backend.live import _current_race_lap

    start = datetime(2025, 8, 31, 13, 0, tzinfo=timezone.utc)
    collapsed = [{"lap_number": i, "date_start": start.isoformat()} for i in range(1, 20)]
    assert _current_race_lap(collapsed, start, start, 0) == 1
    clock = start + timedelta(seconds=12)
    assert _current_race_lap(collapsed, clock, start, 0) == 1
    later = start + timedelta(seconds=90 * 5)
    dated = [
        {"lap_number": i, "date_start": (start + timedelta(seconds=90 * i)).isoformat()}
        for i in range(1, 12)
    ]
    assert _current_race_lap(dated, later, start, 0) == 5


def test_sse_generator_flushes_first_bytes():
    from backend.live import sse_build_payload, sse_generator

    src = inspect.getsource(sse_generator)
    assert ": connected" in src
    assert '"positions"' in src
    build = inspect.getsource(sse_build_payload)
    assert "asyncio.gather" in build
    assert "seq" in build


def test_quick_analysis_route_registered():
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/aris/quick-analysis" in paths
    assert "/api/circuit/{year}/{round_number}/map" in paths


def test_scheduled_laps_netherlands():
    from backend.calendar import scheduled_laps

    n = scheduled_laps(2025, 15, "Netherlands", "netherlands")
    assert n == 72


def test_quick_analysis_marks_recommended():
    from backend.aris_api import quick_analysis
    from backend.models import StratPlanOut, StratPlansResponse

    payload = StratPlansResponse(
        year=2025,
        round_number=15,
        driver_code="VER",
        plans=[
            StratPlanOut(id="a", name="One stop", pit_laps=[28], pit_compounds=["H"], start_compound="M", recommended=False),
            StratPlanOut(id="b", name="Two stop", pit_laps=[18, 42], pit_compounds=["M", "H"], start_compound="S", recommended=False),
            StratPlanOut(id="c", name="Alt", pit_laps=[33], pit_compounds=["H"], start_compound="M", recommended=False),
        ],
    )

    def fake_plans(*_a, **_k):
        return payload

    import backend.aris_api as api

    orig = api.plans
    api.plans = fake_plans  # type: ignore[method-assign]
    try:
        out = quick_analysis(2025, 15, "VER")
        assert len(out.plans) == 3
        assert out.plans[0].recommended is True
        assert sum(1 for p in out.plans if p.recommended) == 1
    finally:
        api.plans = orig
