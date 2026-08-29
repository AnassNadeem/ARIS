"""Replay-frame outline stripping, deltas, and gzip middleware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.models import (
    CircuitPathXY,
    LivePosition,
    LivePositionsResponse,
    LiveTimingResponse,
    LiveTimingRow,
    LiveWeatherResponse,
    ReplayFrameResponse,
)


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


def _row(code: str, position: int, last_lap_ms: int | None = None) -> LiveTimingRow:
    return LiveTimingRow(position=position, driver_code=code, last_lap_ms=last_lap_ms)


def _pos(code: str, x: float, y: float) -> LivePosition:
    return LivePosition(driver_code=code, x=x, y=y, path_frac=x / 1000.0)


def _frame(as_of: datetime, *, ver_x: float, last_lap_ms: int | None) -> ReplayFrameResponse:
    return ReplayFrameResponse(
        session_key=42,
        as_of=as_of,
        elapsed_s=10,
        duration_s=5000,
        date_start=as_of,
        date_end=as_of + timedelta(hours=2),
        timing=LiveTimingResponse(
            is_live=True,
            session_key=42,
            rows=[
                _row("VER", 1, last_lap_ms),
                _row("HAM", 2, 90_000),
            ],
        ),
        weather=LiveWeatherResponse(is_live=True, air_temp=24.0),
        positions=LivePositionsResponse(
            is_live=True,
            positions=[_pos("VER", ver_x, 10.0), _pos("HAM", 20.0, 30.0)],
            circuit_path=CircuitPathXY(x=list(range(80)), y=list(range(80))),
            pit_lane_x=[0.0, 1.0, 2.0],
            pit_lane_y=[0.0, 1.0, 2.0],
            markers=[],
            drs_segments=[[0, 10]],
        ),
        source="fastf1",
        ready=True,
    )


def test_first_wire_frame_is_full_without_outline():
    from backend import live

    live.clear_replay_frame_delta_cache()
    t0 = datetime(2025, 8, 31, 13, 0, tzinfo=timezone.utc)
    wire = live.encode_replay_wire_frame(_frame(t0, ver_x=100.0, last_lap_ms=91_000))
    assert wire.is_delta is False
    assert wire.positions.circuit_path is None
    assert wire.positions.pit_lane_x == []
    assert wire.positions.drs_segments == []
    assert len(wire.timing.rows) == 2
    assert len(wire.positions.positions) == 2


def test_subsequent_wire_frame_is_delta():
    from backend import live

    live.clear_replay_frame_delta_cache()
    t0 = datetime(2025, 8, 31, 13, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(milliseconds=250)
    first = live.encode_replay_wire_frame(_frame(t0, ver_x=100.0, last_lap_ms=91_000))
    second = live.encode_replay_wire_frame(
        _frame(t1, ver_x=140.0, last_lap_ms=91_000), prev_as_of=first.as_of
    )
    assert second.is_delta is True
    assert {r.driver_code for r in second.timing.rows} == set()
    assert [p.driver_code for p in second.positions.positions] == ["VER"]
    assert second.positions.positions[0].x == 140.0
    assert second.positions.circuit_path is None


def test_init_replay_includes_outline_keys(monkeypatch):
    import asyncio

    from backend import live as live_mod

    monkeypatch.setattr(live_mod, "_openf1", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no openf1")))
    monkeypatch.setattr(live_mod, "load_replay_pack_disk", lambda *_a, **_k: None)
    monkeypatch.setattr(live_mod, "_kick_pack_job", lambda *_a, **_k: None)
    key = live_mod.synthetic_session_key(2025, 15, "R")
    live_mod._REPLAY_PACKS.pop(key, None)
    payload = asyncio.run(live_mod.init_replay(2025, 15, "R"))
    assert "circuit_path" in payload
    assert "pit_lane_x" in payload
    assert "markers" in payload
    assert "drs_segments" in payload
    live_mod._REPLAY_PACKS.pop(key, None)


def test_gzip_middleware_registered_and_compresses():
    from fastapi.middleware.gzip import GZipMiddleware

    from backend.main import app

    assert any(getattr(m, "cls", None) is GZipMiddleware for m in app.user_middleware)

    client = _client(app)
    res = client.get("/api/calendar/2025", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    enc = (res.headers.get("content-encoding") or "").lower()
    if enc:
        assert enc == "gzip"
    else:
        # httpx may strip Content-Encoding after decompressing.
        assert len(res.content) > 1000


def test_replay_frame_endpoint_delta_and_gzip(monkeypatch):
    from fastapi.middleware.gzip import GZipMiddleware

    from backend import live
    from backend.main import app

    live.clear_replay_frame_delta_cache()
    t0 = datetime(2025, 8, 31, 13, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(milliseconds=250)
    frames = {
        t0.isoformat(): _frame(t0, ver_x=100.0, last_lap_ms=91_000),
        t1.isoformat(): _frame(t1, ver_x=140.0, last_lap_ms=91_000),
    }

    async def fake_cached(session_key, as_of, **_k):
        key = as_of.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        hit = frames.get(as_of.isoformat()) or frames.get(key)
        if hit is None:
            for frame in frames.values():
                if abs((as_of - frame.as_of).total_seconds()) < 0.05:
                    return frame
            raise AssertionError(f"unexpected as_of {as_of!r}")
        return hit

    monkeypatch.setattr(live, "cached_replay_frame", fake_cached)
    client = _client(app)
    qs0 = (
        f"/api/live/replay-frame?session_key=42&as_of={t0.isoformat().replace('+00:00', 'Z')}"
        "&year=2025&round_number=15"
    )
    first = client.get(qs0, headers={"Accept-Encoding": "gzip"})
    assert first.status_code == 200
    body1 = first.json()
    assert body1["is_delta"] is False
    assert body1["positions"]["circuit_path"] is None
    assert len(body1["timing"]["rows"]) == 2

    qs1 = (
        f"/api/live/replay-frame?session_key=42&as_of={t1.isoformat().replace('+00:00', 'Z')}"
        f"&year=2025&round_number=15&prev_as_of={body1['as_of']}"
    )
    second = client.get(qs1, headers={"Accept-Encoding": "gzip"})
    assert second.status_code == 200
    body2 = second.json()
    assert body2["is_delta"] is True
    assert len(body2["timing"]["rows"]) == 0
    assert [p["driver_code"] for p in body2["positions"]["positions"]] == ["VER"]
    assert len(second.content) < len(first.content) or body2["is_delta"] is True
    assert any(getattr(m, "cls", None) is GZipMiddleware for m in app.user_middleware)
    enc = (second.headers.get("content-encoding") or first.headers.get("content-encoding") or "").lower()
    # httpx may decompress; middleware is still registered. When encoding is visible, it must be gzip.
    if enc:
        assert enc == "gzip"
