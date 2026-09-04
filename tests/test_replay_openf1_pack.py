"""OpenF1 fallback for recent replay packs FastF1 cannot load yet."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.live import (
    _PACK_LOAD_ERROR,
    _apply_openf1_to_pack,
    _attach_synthetic_gps,
    _codes_from_openf1_drivers,
    _new_replay_pack,
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
    start = datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc)
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
    assert 801_026_131 not in _PACK_LOAD_ERROR


def test_fill_pack_openf1_uses_resolved_session(monkeypatch):
    import asyncio

    from backend import live as live_mod

    pack = _new_replay_pack(
        801_026_131,
        2026,
        13,
        "FP1",
        datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc),
        None,
    )
    calls: list[str] = []

    async def fake_resolve(year, round_number, session_type):
        assert (year, round_number, session_type) == (2026, 13, "FP1")
        return {"session_key": 7777, "date_start": "2026-09-04T10:30:00Z", "date_end": "2026-09-04T11:40:00Z"}

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
