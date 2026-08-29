"""Backend perf: /api/status alias, SSE seq + keys, parallel tick budget."""

from __future__ import annotations

import asyncio
import inspect
import json

from backend.models import (
    LivePositionsResponse,
    LiveStatus,
    LiveTimingResponse,
    LiveWeatherResponse,
)


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


def test_status_route_registered():
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/status" in paths
    assert "/api/aris/stats" in paths


def test_api_status_same_shape_as_aris_stats():
    from backend.main import app

    client = _client(app)
    stats = client.get("/api/aris/stats")
    status = client.get("/api/status")
    assert stats.status_code == 200
    assert status.status_code == 200
    a = stats.json()
    b = status.json()
    assert a == b
    for key in (
        "lap_time_mae_s",
        "decision_match_rate",
        "never_pit_baseline",
        "avg_position_delta",
        "clean_delta",
        "disrupted_delta",
        "version",
        "match_rate",
        "match_rate_fraction",
        "last_gate",
        "timestamp",
    ):
        assert key in b
    assert b["match_rate"] == b["decision_match_rate"]
    assert b["version"]


def test_sse_events_have_seq_status_timing_weather_positions(monkeypatch):
    from backend import live

    async def fake_status(**_k):
        return LiveStatus(is_live=False, year=2026, round_number=15)

    async def fake_timing(**_k):
        return LiveTimingResponse(is_live=False, rows=[])

    async def fake_weather(**_k):
        return LiveWeatherResponse(is_live=False)

    async def fake_positions(**_k):
        return LivePositionsResponse(is_live=False, positions=[])

    monkeypatch.setattr(live, "live_status", fake_status)
    monkeypatch.setattr(live, "live_timing", fake_timing)
    monkeypatch.setattr(live, "live_weather", fake_weather)
    monkeypatch.setattr(live, "live_positions", fake_positions)

    payload, _ms, meta = asyncio.run(live.sse_build_payload(None, 1, None))
    assert payload["seq"] == 1
    assert payload["last_updated"]
    assert payload["full"] is True
    assert "status" in payload and "is_live" in payload["status"]
    assert "timing" in payload
    assert "weather" in payload
    assert "positions" in payload
    assert meta == (None, 2026, 15)

    # Second tick with the same session meta omits static circuit_path.
    payload2, _ms2, _meta2 = asyncio.run(live.sse_build_payload(None, 2, meta))
    assert payload2["seq"] == 2
    assert payload2["full"] is False
    assert "circuit_path" not in (payload2.get("positions") or {})

    src = inspect.getsource(live.sse_generator)
    assert "seq" in src
    assert "last_updated" in src


def test_sse_stream_handshake_and_seq(monkeypatch):
    from backend import live

    async def fake_status(**_k):
        return LiveStatus(is_live=False)

    async def fake_timing(**_k):
        return LiveTimingResponse(is_live=False, rows=[])

    async def fake_weather(**_k):
        return LiveWeatherResponse(is_live=False)

    async def fake_positions(**_k):
        return LivePositionsResponse(is_live=False, positions=[])

    monkeypatch.setattr(live, "live_status", fake_status)
    monkeypatch.setattr(live, "live_timing", fake_timing)
    monkeypatch.setattr(live, "live_weather", fake_weather)
    monkeypatch.setattr(live, "live_positions", fake_positions)

    # Don't sleep between ticks in this unit test.
    orig_sleep = live.asyncio.sleep

    async def _no_sleep(_delay=0):
        return None

    monkeypatch.setattr(live.asyncio, "sleep", _no_sleep)

    async def _collect() -> list[dict]:
        events: list[dict] = []
        agen = live.sse_generator()
        try:
            async for chunk in agen:
                for line in chunk.splitlines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
                if len(events) >= 2:
                    break
        finally:
            await agen.aclose()
        return events

    async def _main() -> list[dict]:
        return await asyncio.wait_for(_collect(), timeout=5)

    events = asyncio.run(_main())
    monkeypatch.setattr(live.asyncio, "sleep", orig_sleep)
    assert events[0]["seq"] == 0
    assert "status" in events[0]
    assert "timing" in events[0]
    assert "weather" in events[0]
    assert "positions" in events[0]
    assert events[1]["seq"] == 1
    assert "last_updated" in events[1]
    assert "status" in events[1]
    assert "timing" in events[1]
    assert "weather" in events[1]
    assert "positions" in events[1]


def test_sse_tick_warm_average_under_500ms(monkeypatch):
    from backend import live

    async def fake_status(**_k):
        await asyncio.sleep(0.12)
        return LiveStatus(is_live=False, year=2026, round_number=15)

    async def fake_timing(**_k):
        await asyncio.sleep(0.12)
        return LiveTimingResponse(is_live=False, rows=[])

    async def fake_weather(**_k):
        await asyncio.sleep(0.12)
        return LiveWeatherResponse(is_live=False)

    async def fake_positions(**_k):
        await asyncio.sleep(0.12)
        return LivePositionsResponse(is_live=False, positions=[])

    monkeypatch.setattr(live, "live_status", fake_status)
    monkeypatch.setattr(live, "live_timing", fake_timing)
    monkeypatch.setattr(live, "live_weather", fake_weather)
    monkeypatch.setattr(live, "live_positions", fake_positions)

    async def _run() -> list[float]:
        times: list[float] = []
        meta = None
        for i in range(10):
            _payload, ms, meta = await live.sse_build_payload(None, i + 1, meta)
            times.append(ms)
        return times

    times = asyncio.run(_run())
    avg = sum(times) / len(times)
    # Sequential 0.12*4 = 480ms plus overhead; parallel should stay ~240ms (status + one 0.12 gather).
    assert avg < 500, f"warm SSE tick average {avg:.0f}ms"
    assert avg < 400, f"expected parallel gather (~240ms), got {avg:.0f}ms"


def test_put_both_warms_memory_cache():
    from backend.cache import cache, put_both

    put_both("perf_test_key", {"ok": True}, 60)
    assert cache.get("perf_test_key", 60) == {"ok": True}
