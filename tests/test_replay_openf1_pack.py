"""OpenF1 fallback for recent replay packs FastF1 cannot load yet."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.live import (
    _PACK_LOAD_ERROR,
    _apply_openf1_to_pack,
    _attach_synthetic_gps,
    _codes_from_openf1_drivers,
    _new_replay_pack,
    _openf1_pack_playable,
    _prefer_openf1_pack,
    _stamp_openf1_driver_codes,
    replay_pack_stage,
)


def test_codes_from_openf1_drivers():
    codes, colours = _codes_from_openf1_drivers(
        [
            {"driver_number": 1, "name_acronym": "VER", "team_colour": "3671C6"},
            {"driver_number": 16, "name_acronym": "LEC", "team_colour": "E8002D"},
            {"driver_number": 44, "broadcast_name": "HAM"},
        ]
    )
    assert codes[1] == "VER"
    assert codes[16] == "LEC"
    assert codes[44] == "HAM"
    assert colours[1] == "#3671C6"
    assert colours[16] == "#E8002D"


def test_stamp_openf1_driver_codes_fills_missing_acronyms():
    rows = _stamp_openf1_driver_codes(
        [
            {"driver_number": 1, "lap_number": 3, "date_start": "2026-09-04T10:35:00+00:00"},
            {"driver_number": 16, "driver_code": "LEC", "lap_number": 2},
        ],
        {1: "VER", 16: "LEC"},
    )
    assert rows[0]["driver_code"] == "VER"
    assert rows[1]["driver_code"] == "LEC"


def test_apply_openf1_to_pack_reaches_minimal_with_synthetic_gps():
    start = datetime(2026, 9, 4, 10, 30, tzinfo=UTC)
    pack = _new_replay_pack(801_026_131, 2026, 13, "FP1", start, None)
    pack["path_x"] = [0.0, 10.0, 10.0, 0.0, 0.0]
    pack["path_y"] = [0.0, 0.0, 10.0, 10.0, 0.0]
    _PACK_LOAD_ERROR[801_026_131] = "FastF1 replay assets unavailable"

    _apply_openf1_to_pack(
        pack,
        session={
            "session_key": 9991,
            "date_start": "2026-09-04T10:30:00+00:00",
            "date_end": "2026-09-04T11:40:00+00:00",
        },
        drivers=[{"driver_number": 1, "name_acronym": "VER", "team_colour": "3671C6"}],
        laps=[
            {
                "driver_number": 1,
                "lap_number": 1,
                "date_start": "2026-09-04T10:32:00+00:00",
                "lap_duration": 84.2,
                "duration_sector_1": 27.1,
                "is_pit_out_lap": True,
            }
        ],
        stints=[{"driver_number": 1, "stint_number": 1, "compound": "SOFT", "lap_start": 1}],
        positions=[{"driver_number": 1, "position": 3, "date": "2026-09-04T10:32:10+00:00"}],
        weather=[{"date": "2026-09-04T10:32:00+00:00", "rainfall": False}],
        race_control=[],
    )
    _PACK_LOAD_ERROR.pop(801_026_131, None)
    _attach_synthetic_gps(pack)
    pack["stage"] = "minimal"

    assert pack["source"] == "openf1"
    assert pack["openf1_session_key"] == 9991
    assert pack["codes"][1] == "VER"
    assert pack["laps"][0]["driver_code"] == "VER"
    assert pack["stints"][0]["compound"] == "SOFT"
    assert replay_pack_stage(pack) == "minimal"
    assert (pack.get("ff1") or {}).get("synthetic_gps") is True
    assert "VER" in ((pack.get("ff1") or {}).get("pos_samples") or {})
    samples = (pack.get("ff1") or {}).get("pos_samples")["VER"]
    # ~80s lap at 0.5s steps should be tens of points, not 4–6 sector ticks.
    assert len(samples) >= 20
    assert 801_026_131 not in _PACK_LOAD_ERROR


def test_fill_pack_openf1_uses_resolved_session(monkeypatch):
    import asyncio

    from backend import live as live_mod

    pack = _new_replay_pack(
        801_026_131,
        2026,
        13,
        "FP1",
        datetime(2026, 9, 4, 10, 30, tzinfo=UTC),
        None,
    )
    calls: list[str] = []

    async def fake_resolve(year, round_number, session_type):
        assert (year, round_number, session_type) == (2026, 13, "FP1")
        return {
            "session_key": 7777,
            "date_start": "2026-09-04T10:30:00Z",
            "date_end": "2026-09-04T11:40:00Z",
        }

    async def fake_openf1(path, params=None, *, timeout=None):
        calls.append(path)
        if path == "drivers":
            return [{"driver_number": 81, "name_acronym": "PIA", "team_colour": "FF8000"}]
        if path == "laps":
            return [
                {
                    "driver_number": 81,
                    "lap_number": 4,
                    "date_start": "2026-09-04T10:40:00Z",
                    "lap_duration": 83.1,
                }
            ]
        if path == "stints":
            return [{"driver_number": 81, "compound": "MEDIUM", "lap_start": 1}]
        return []

    monkeypatch.setattr(live_mod, "resolve_openf1_session", fake_resolve)
    monkeypatch.setattr(live_mod, "_openf1", fake_openf1)

    ok = asyncio.run(live_mod._fill_pack_openf1(pack, 801_026_131, 2026, 13, "FP1"))
    assert ok is True
    assert pack["source"] == "openf1"
    assert pack["openf1_session_key"] == 7777
    assert pack["laps"][0]["driver_code"] == "PIA"
    assert "laps" in calls
    assert "drivers" in calls


def test_synthetic_pos_from_laps_is_dense():
    from backend.sessions import synthetic_pos_from_laps

    laps = [
        {
            "driver_code": "VER",
            "lap_number": 1,
            "date_start": "2026-09-04T10:32:00+00:00",
            "lap_duration": 90.0,
        }
    ]
    samples = synthetic_pos_from_laps(
        laps, [0.0, 10.0, 10.0, 0.0, 0.0], [0.0, 0.0, 10.0, 10.0, 0.0]
    )
    assert len(samples["VER"]) >= 80


def test_prefer_openf1_pack_for_practice_only():
    assert _prefer_openf1_pack("FP1") is True
    assert _prefer_openf1_pack("FP2") is True
    assert _prefer_openf1_pack("fp3") is True
    assert _prefer_openf1_pack("R") is False
    assert _prefer_openf1_pack("Q") is False


def test_openf1_playable_pack_reports_full_stage():
    start = datetime(2026, 9, 4, 10, 30, tzinfo=UTC)
    pack = _new_replay_pack(801_026_131, 2026, 13, "FP1", start, None)
    pack["laps"] = [{"driver_number": 1, "lap_number": 1, "driver_code": "VER"}]
    pack["source"] = "openf1"
    pack["openf1_session_key"] = 11354
    pack["stage"] = "full"
    assert _openf1_pack_playable(pack) is True
    assert replay_pack_stage(pack) == "full"


def test_cold_load_practice_skips_fastf1_when_openf1_ok(monkeypatch):
    import asyncio

    from backend import live as live_mod

    start = datetime(2026, 9, 4, 10, 30, tzinfo=UTC)
    key = live_mod.synthetic_session_key(2026, 13, "FP1")
    live_mod._REPLAY_PACKS.pop(key, None)
    live_mod._PACK_LOAD_ERROR.pop(key, None)
    ff1_calls: list[str] = []

    async def fake_map(session_key, year, round_number, *, executor=None):
        pack = live_mod._REPLAY_PACKS[session_key]
        pack["path_x"] = [0.0, 10.0, 10.0, 0.0, 0.0]
        pack["path_y"] = [0.0, 0.0, 10.0, 10.0, 0.0]

    async def fake_openf1(pack, session_key, year, round_number, mapped):
        pack["laps"] = [
            {
                "driver_number": 1,
                "driver_code": "VER",
                "lap_number": 1,
                "date_start": "2026-09-04T10:32:00+00:00",
                "lap_duration": 84.0,
            }
        ]
        pack["codes"] = {1: "VER"}
        pack["source"] = "openf1"
        pack["openf1_session_key"] = 11354
        pack["date_start"] = start
        return True

    async def fake_seed(_pack):
        return None

    async def boom_ff1(*_a, **_k):
        ff1_calls.append("fastf1")
        raise AssertionError("FastF1 must not run when OpenF1 practice pack succeeds")

    monkeypatch.setattr(live_mod, "_calendar_session_status", lambda *_a, **_k: "COMPLETED")
    monkeypatch.setattr(live_mod, "_fill_pack_map", fake_map)
    monkeypatch.setattr(live_mod, "_fill_pack_openf1", fake_openf1)
    monkeypatch.setattr(live_mod, "_seed_openf1_location_gps", fake_seed)
    monkeypatch.setattr(live_mod, "_upgrade_pack_fastf1", boom_ff1)
    monkeypatch.setattr(live_mod, "save_replay_pack_disk", lambda *_a, **_k: True)
    monkeypatch.setattr(
        live_mod,
        "calendar_session_window",
        lambda *_a, **_k: (start, start.replace(hour=11, minute=40)),
    )

    pack, need_gps = asyncio.run(live_mod._cold_load_minimal(key, 2026, 13, "FP1"))
    assert ff1_calls == []
    assert need_gps is False
    assert pack["source"] == "openf1"
    assert pack["laps"]
    assert replay_pack_stage(pack) == "full"
    assert key not in live_mod._PACK_LOAD_ERROR
    live_mod._REPLAY_PACKS.pop(key, None)


def test_peek_status_does_not_rekick_openf1_full_pack(monkeypatch):
    import asyncio

    from backend import live as live_mod

    start = datetime(2026, 9, 4, 10, 30, tzinfo=UTC)
    key = live_mod.synthetic_session_key(2026, 13, "FP2")
    pack = _new_replay_pack(key, 2026, 13, "FP2", start, None)
    pack["laps"] = [{"driver_number": 81, "driver_code": "PIA", "lap_number": 1}]
    pack["source"] = "openf1"
    pack["openf1_session_key"] = 11355
    pack["stage"] = "full"
    live_mod._REPLAY_PACKS[key] = pack
    kicks: list[int] = []

    def boom_kick(session_key, *_a, **_k):
        kicks.append(session_key)
        raise AssertionError("OpenF1 practice pack must not re-kick FastF1")

    monkeypatch.setattr(live_mod, "_kick_pack_job", boom_kick)
    monkeypatch.setattr(live_mod, "hydrate_replay_pack_cache", lambda *_a, **_k: (pack, True, False))
    out = asyncio.run(live_mod.peek_replay_pack_status(key, 2026, 13, "FP2"))
    assert kicks == []
    assert out["stage"] == "full"
    assert out["source"] == "openf1"
    pack["stage"] = "minimal"
    out_min = asyncio.run(live_mod.peek_replay_pack_status(key, 2026, 13, "FP2"))
    assert kicks == []
    assert out_min["ready"] is True
    live_mod._REPLAY_PACKS.pop(key, None)


def test_location_bucket_nowait_uses_cache(monkeypatch):
    import asyncio

    from backend import live as live_mod

    clock = datetime(2026, 9, 4, 10, 32, tzinfo=UTC)
    live_mod._LOC_BUCKETS.clear()
    live_mod._LOC_INFLIGHT.clear()
    cache_key = live_mod._loc_bucket_id(11354, clock)
    live_mod._LOC_BUCKETS[cache_key] = [{"driver_number": 1, "x": -920, "y": 2410}]

    async def boom(*_a, **_k):
        raise AssertionError("cached OpenF1 location must not refetch")

    monkeypatch.setattr(live_mod, "_location_bucket", boom)
    rows = asyncio.run(live_mod._location_bucket_nowait(11354, clock))
    assert rows[0]["x"] == -920
    live_mod._LOC_BUCKETS.clear()
    live_mod._LOC_INFLIGHT.clear()
