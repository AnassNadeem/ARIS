"""Live session calendar windows and OpenF1 helper parsing — no network."""

from datetime import UTC, datetime, timezone

from backend.cache import TTL_NEXT_RACE
from backend.calendar import _session_status, get_round_sessions
from backend.http_client import openf1_url
from backend.live import _sector_colour_from_segments, _session_type_map, _session_window_live


def test_ttl_next_race_is_short():
    assert TTL_NEXT_RACE <= 30


def test_replay_pack_complete_after_session_end():
    from backend.live import replay_pack_is_complete

    pack = {"date_end": datetime(2025, 8, 31, 15, 0, tzinfo=timezone.utc)}
    assert replay_pack_is_complete(pack, datetime(2025, 8, 31, 15, 10, tzinfo=timezone.utc))
    assert not replay_pack_is_complete(pack, datetime(2025, 8, 31, 14, 59, tzinfo=timezone.utc))


def test_circuit_match_ignores_accents_and_country_name():
    from types import SimpleNamespace

    from backend.live import _circuit_match, synthetic_session_key

    brazil = SimpleNamespace(city="Sao Paulo", circuit_name="Interlagos", name="Sao Paulo", circuit_key="brazil", country="Brazil")
    sess = {"circuit_short_name": "Interlagos", "location": "São Paulo", "country_name": "Brazil", "country_code": "BRA"}
    assert _circuit_match(sess, brazil)
    italy_monza = SimpleNamespace(city="Monza", circuit_name="Monza", name="Italy", circuit_key="monza", country="Italy")
    imola = {"circuit_short_name": "Imola", "location": "Imola", "country_name": "Italy", "country_code": "ITA"}
    assert not _circuit_match(imola, italy_monza)
    assert synthetic_session_key(2025, 15, "R") == 800_000_000 + 2025 * 1000 + 15 * 10 + 7


def test_decode_synthetic_session_key_roundtrip():
    from backend.live import decode_synthetic_session_key, is_synthetic_session_key, synthetic_session_key

    key = synthetic_session_key(2026, 16, "Q")
    assert is_synthetic_session_key(key)
    assert decode_synthetic_session_key(key) == (2026, 16, "Q")
    assert decode_synthetic_session_key(9158) is None


def test_live_status_replay_skips_openf1(monkeypatch):
    import asyncio

    from backend import live as live_mod

    async def boom(*_a, **_k):
        raise AssertionError("OpenF1 must not be called for replay status")

    monkeypatch.setattr(live_mod, "_openf1", boom)
    monkeypatch.setattr(live_mod, "load_replay_pack_disk", lambda *_a, **_k: None)
    key = live_mod.synthetic_session_key(2025, 15, "R")
    live_mod._REPLAY_PACKS.pop(key, None)
    status = asyncio.run(live_mod.live_status(replay_session_key=key))
    assert status.replay_mode is True
    assert status.year == 2025
    assert status.round_number == 15
    assert status.session_type == "R"
    assert status.source == "fastf1"


def test_ensure_replay_pack_miss_does_not_call_openf1(monkeypatch):
    import asyncio
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from backend import live as live_mod

    async def boom(*_a, **_k):
        raise AssertionError("OpenF1 must not be called for replay packs")

    monkeypatch.setattr(live_mod, "_openf1", boom)
    monkeypatch.setattr(live_mod, "load_replay_pack_disk", lambda *_a, **_k: None)
    monkeypatch.setattr(live_mod, "save_replay_pack_disk", lambda *_a, **_k: True)

    cmap = SimpleNamespace(
        available=True,
        x=[0.0, 10.0, 10.0, 0.0],
        y=[0.0, 0.0, 10.0, 10.0],
        bounds=None,
        pit_stalls=[],
        pit_lane_x=[],
        pit_lane_y=[],
        markers=[],
        drs_segments=[],
    )
    start = datetime(2025, 3, 2, 15, 0, tzinfo=timezone.utc)

    def fake_assets(*_a, **_k):
        return {
            "ok": True,
            "session_type": "R",
            "code_by_num": {1: "VER"},
            "num_by_code": {"VER": 1},
            "colours": {1: "#00ff00"},
            "q_times": {},
            "status_by_code": {},
            "laps": [
                {
                    "driver_number": 1,
                    "driver_code": "VER",
                    "lap_number": 1,
                    "date_start": start.isoformat(),
                    "lap_duration": 90.0,
                    "position": 1,
                }
            ],
            "weather": [],
            "pos_samples": {"VER": [(start.timestamp(), 0.0, 0.0, "OnTrack")]},
            "car_samples": {},
            "quali_windows": [],
            "stints": [],
            "positions": [],
            "race_control": [],
            "date_start": start,
            "date_end": datetime(2025, 3, 2, 17, 0, tzinfo=timezone.utc),
        }

    monkeypatch.setattr("backend.sessions.circuit_map_quick", lambda *_a, **_k: cmap)
    monkeypatch.setattr("backend.sessions.build_ff1_replay_assets", fake_assets)
    monkeypatch.setattr("backend.sessions.pit_lane_from_path", lambda *_a, **_k: ([], [], []))
    monkeypatch.setattr("backend.sessions.pit_lane_from_samples", lambda *_a, **_k: None)

    key = live_mod.synthetic_session_key(2025, 1, "R")
    live_mod._REPLAY_PACKS.pop(key, None)
    pack = asyncio.run(live_mod._ensure_replay_pack(key, 2025, 1, session_type="R"))
    assert pack.get("source") == "fastf1"
    assert pack.get("ff1", {}).get("pos_samples")
    assert pack.get("codes", {}).get(1) == "VER"
    live_mod._REPLAY_PACKS.pop(key, None)


def test_ensure_replay_pack_minimal_does_not_wait_for_gps(monkeypatch):
    import asyncio
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from backend import live as live_mod

    async def boom(*_a, **_k):
        raise AssertionError("OpenF1 must not be called for replay packs")

    monkeypatch.setattr(live_mod, "_openf1", boom)
    monkeypatch.setattr(live_mod, "load_replay_pack_disk", lambda *_a, **_k: None)
    monkeypatch.setattr(live_mod, "save_replay_pack_disk", lambda *_a, **_k: True)

    cmap = SimpleNamespace(
        available=True,
        x=[0.0, 10.0, 10.0, 0.0],
        y=[0.0, 0.0, 10.0, 10.0],
        bounds=None,
        pit_stalls=[],
        pit_lane_x=[],
        pit_lane_y=[],
        markers=[],
        drs_segments=[],
    )
    start = datetime(2025, 3, 2, 15, 0, tzinfo=timezone.utc)
    calls: list[bool] = []

    def fake_assets(*_a, **k):
        tel = k.get("telemetry", True)
        calls.append(bool(tel))
        return {
            "ok": True,
            "session_type": "R",
            "code_by_num": {1: "VER"},
            "num_by_code": {"VER": 1},
            "colours": {1: "#00ff00"},
            "q_times": {},
            "status_by_code": {},
            "laps": [
                {
                    "driver_number": 1,
                    "driver_code": "VER",
                    "lap_number": 1,
                    "date_start": start.isoformat(),
                    "lap_duration": 90.0,
                    "position": 1,
                }
            ],
            "weather": [{"date": start.isoformat(), "air_temperature": 22}] if tel else [],
            "pos_samples": {"VER": [(start.timestamp(), 0.0, 0.0, "OnTrack")]} if tel else {},
            "car_samples": {},
            "quali_windows": [],
            "stints": [],
            "positions": [],
            "race_control": [],
            "date_start": start,
            "date_end": datetime(2025, 3, 2, 17, 0, tzinfo=timezone.utc),
            "synthetic_gps": False,
        }

    monkeypatch.setattr("backend.sessions.circuit_map_quick", lambda *_a, **_k: cmap)
    monkeypatch.setattr("backend.sessions.build_ff1_replay_assets", fake_assets)
    monkeypatch.setattr("backend.sessions.pit_lane_from_path", lambda *_a, **_k: ([], [], []))
    monkeypatch.setattr("backend.sessions.pit_lane_from_samples", lambda *_a, **_k: None)

    key = live_mod.synthetic_session_key(2025, 1, "R")
    live_mod._REPLAY_PACKS.pop(key, None)
    live_mod._PACK_JOBS.pop(key, None)

    async def _run():
        pack = await live_mod._ensure_replay_pack(key, 2025, 1, session_type="R", wait_for="minimal")
        assert pack.get("laps")
        assert live_mod.replay_pack_stage(pack) in {"minimal", "full"}
        assert live_mod._pack_status_label(key) == "ready"
        status = await live_mod.peek_replay_pack_status(key, 2025, 1, "R")
        assert status["ready"] is True
        assert status["flags"]["laps_ready"] is True
        full = await live_mod._ensure_replay_pack(key, 2025, 1, session_type="R", wait_for="full")
        assert live_mod._ff1_pack_ready(full)
        assert live_mod.replay_pack_stage(full) == "full"

    asyncio.run(_run())
    assert False in calls
    assert True in calls
    live_mod._REPLAY_PACKS.pop(key, None)


def test_ff1_pack_ready_ignores_synthetic_gps():
    from backend.live import _ff1_pack_ready, replay_pack_stage

    pack = {
        "source": "fastf1",
        "laps": [{"driver_code": "VER"}],
        "stage": "minimal",
        "ff1": {"pos_samples": {"VER": [(1.0, 0.0, 0.0, "OnTrack")]}, "synthetic_gps": True},
    }
    assert _ff1_pack_ready(pack) is False
    assert replay_pack_stage(pack) == "minimal"


def test_ensure_replay_pack_disk_full_skips_fastf1(monkeypatch):
    import asyncio

    from backend import live as live_mod

    key = live_mod.synthetic_session_key(2025, 15, "R")
    pack = {
        "laps": [{"driver_number": 1, "lap_number": 1}],
        "year": 2025,
        "round_number": 15,
        "session_type": "R",
        "session_status": "COMPLETED",
        "stage": "full",
        "source": "fastf1",
        "ff1": {"pos_samples": {"VER": [(0.0, 0.0, 0.0, "OnTrack")]}, "synthetic_gps": False},
        "path_traces": {"VER": {"x": [0.0], "y": [0.0]}},
        "path_traces_v": live_mod._PATH_TRACES_V,
    }
    live_mod._REPLAY_PACKS.pop(key, None)

    def boom_kick(*_a, **_k):
        raise AssertionError("FastF1 must not run for a full disk replay pack")

    monkeypatch.setattr(live_mod, "load_replay_pack_disk", lambda *_a, **_k: pack)
    monkeypatch.setattr(live_mod, "_kick_pack_job", boom_kick)

    out = asyncio.run(live_mod._ensure_replay_pack(key, 2025, 15, session_type="R", wait_for="full"))
    assert out["stage"] == "full"
    assert live_mod._ff1_pack_ready(out)
    live_mod._REPLAY_PACKS.pop(key, None)


def test_init_replay_returns_metadata_without_openf1(monkeypatch):
    import asyncio

    from backend import live as live_mod

    async def boom(*_a, **_k):
        raise AssertionError("OpenF1 must not be called for replay init")

    monkeypatch.setattr(live_mod, "_openf1", boom)
    monkeypatch.setattr(live_mod, "load_replay_pack_disk", lambda *_a, **_k: None)
    monkeypatch.setattr(live_mod, "_kick_pack_job", lambda *_a, **_k: None)

    key = live_mod.synthetic_session_key(2025, 15, "R")
    live_mod._REPLAY_PACKS.pop(key, None)
    payload = asyncio.run(live_mod.init_replay(2025, 15, "R"))
    assert payload["session_key"] == key
    assert payload["stage"] in {"metadata", "minimal", "full"}
    assert payload["source"] in {"fastf1", "none"}
    assert payload["session_status"]
    live_mod._REPLAY_PACKS.pop(key, None)


def test_pack_matches_request():
    from backend.live import pack_matches_request

    pack = {"year": 2025, "round_number": 15, "laps": []}
    assert pack_matches_request(pack, 2025, 15)
    assert not pack_matches_request(pack, 2025, 16)
    assert not pack_matches_request(pack, 2024, 15)
    assert pack_matches_request(pack, None, None)


def test_ttl_cache_delete_and_invalidate():
    from backend.cache import TTLCache, cache, invalidate

    c = TTLCache()
    c.set("k", 1)
    assert c.get("k", 60) == 1
    c.delete("k")
    assert c.get("k", 60) is None
    cache.set("aris-test-invalidate", {"ok": True})
    invalidate("aris-test-invalidate")
    assert cache.get("aris-test-invalidate", 60) is None


def test_ghost_at_lap_prefers_driver_key():
    from backend import live as live_mod

    live_mod._GHOST_CACHE.clear()
    live_mod._GHOST_CACHE["2025_15_HAM"] = {12: {"driver_code": "HAM", "active": True}}
    live_mod._GHOST_CACHE["2025_15_99"] = {12: {"driver_code": "VER", "active": True}}
    hit, _reason = live_mod._ghost_at_lap(2025, 15, 99, 12, "HAM")
    assert hit is not None
    assert hit["driver_code"] == "HAM"
    live_mod._GHOST_CACHE["2025_15_NOR"] = {}
    ghost, _r = live_mod._ghost_at_lap(2025, 15, 99, 12, "NOR")
    assert ghost is None


def test_precompute_ghost_from_lap_one():
    from backend.live import precompute_ghost_for_session

    laps = []
    for i in range(1, 9):
        laps.append(
            {
                "lap_number": i,
                "real_action": "STAY_OUT",
                "compound": "MEDIUM",
                "tyre_life": i,
                "fuel_kg": 30.0,
                "position": 3,
                "lap_time_s": 74.0,
            }
        )
    session_data = {
        "session_key": 1,
        "session_type": "R",
        "year": 2025,
        "round_no": 15,
        "country": "Netherlands",
        "total_laps": 8,
        "driver_id": 1,
        "laps": laps,
    }
    recs = [
        {
            "lap": 1,
            "label": "Pit lap 4 for HARD",
            "action": {"kind": "pit_lap", "pit_lap": 4, "pit_compound": "HARD"},
        }
    ]
    result = precompute_ghost_for_session(session_data, "VER", recs)
    assert result.get(1) is not None
    assert result[1]["from_lap_one"] is True
    assert result[1]["driver_code"] == "VER"
    assert result.get(8) is not None
    assert result[4]["ghost_cumulative_delta"] < result[1]["ghost_cumulative_delta"]
    assert result[8]["ghost_tyre"] == "HARD"


def test_precompute_ghost_uses_selected_plan_not_recommend_default():
    from backend.live import precompute_ghost_for_session

    laps = []
    for i in range(1, 25):
        laps.append(
            {
                "lap_number": i,
                "real_action": "STAY_OUT",
                "compound": "MEDIUM",
                "tyre_life": i,
                "fuel_kg": 30.0,
                "position": 1,
                "lap_time_s": 74.0,
            }
        )
    session_data = {
        "session_key": 1,
        "session_type": "R",
        "year": 2025,
        "round_no": 15,
        "country": "Netherlands",
        "total_laps": 24,
        "driver_id": 1,
        "laps": laps,
        "plan": {"pit_laps": [20], "compounds": ["HARD"], "label": "user-selected"},
    }
    result = precompute_ghost_for_session(session_data, "VER", [])
    assert result.get(20) is not None
    assert result[20]["plan_pit_laps"] == [20]
    assert result[20]["ghost_tyre"] == "HARD"
    assert result[19]["ghost_tyre"] == "MEDIUM"


def test_ghost_recompute_preserves_history_before_current_lap():
    from backend import live as live_mod

    laps = []
    for i in range(1, 13):
        laps.append(
            {
                "driver_code": "VER",
                "lap_number": i,
                "lap_duration": 74.0,
                "compound": "MEDIUM",
                "tyre_life": i,
                "position": 1,
                "is_pit_in_lap": False,
                "track_status": "1",
            }
        )
    pack = {
        "year": 2025,
        "round_number": 15,
        "session_type": "R",
        "country": "Netherlands",
        "total_laps": 12,
        "laps": laps,
        "session_key": 42,
    }
    live_mod._REPLAY_PACKS[42] = pack
    live_mod._GHOST_CACHE.clear()
    first = live_mod.recompute_ghost_from_plan(
        year=2025,
        round_number=15,
        driver="VER",
        current_lap=1,
        pit_laps=[4],
        compounds=["HARD"],
        session_key=42,
        label="first",
    )
    assert first["ticks"]
    assert any(t["lap"] == 4 and t["aris_action"] == "PIT" for t in first["ticks"])
    second = live_mod.recompute_ghost_from_plan(
        year=2025,
        round_number=15,
        driver="VER",
        current_lap=8,
        pit_laps=[10],
        compounds=["SOFT"],
        session_key=42,
        label="adopted",
    )
    assert all(t["lap"] >= 8 for t in second["ticks"])
    cached = live_mod._GHOST_CACHE[live_mod._ghost_driver_key(2025, 15, "VER")]
    assert cached[4]["plan_pit_laps"] == [4]
    assert cached[10]["plan_pit_laps"] == [10]


def test_ghost_on_track_offsets_path_frac():
    from types import SimpleNamespace

    from backend.live import _ghost_on_track

    ghost = {
        "driver_code": "VER",
        "ghost_cumulative_delta": 9.0,
        "typical_lap_s": 90.0,
        "ghost_tyre": "HARD",
    }
    positions = [SimpleNamespace(driver_code="VER", path_frac=0.10)]
    out = _ghost_on_track(ghost, positions, "VER")
    assert out is not None
    assert abs(out["ghost_position_on_track"] - 0.20) < 1e-6
    assert out["ghost_compound"] == "HARD"


def test_replay_pack_disk_roundtrip():
    from backend.cache import get_disk
    from backend.live import load_replay_pack_disk, replay_pack_disk_key, save_replay_pack_disk

    key = 9_990_001
    disk = get_disk()
    disk.pop(replay_pack_disk_key(key), default=None)
    pack = {
        "laps": [{"driver_number": 1, "lap_number": 1, "lap_duration": 72.1}],
        "date_end": datetime(2025, 8, 31, 15, 0, tzinfo=timezone.utc),
        "source": "openf1",
    }
    assert save_replay_pack_disk(key, pack) is True
    loaded = load_replay_pack_disk(key)
    assert loaded is not None
    assert loaded["laps"][0]["lap_number"] == 1
    disk.pop(replay_pack_disk_key(key), default=None)


def test_pack_cache_key_matches_disk_key():
    from backend.live import replay_pack_disk_key, synthetic_session_key
    from backend.sessions import _pack_cache_key

    assert _pack_cache_key(2025, 15, "R") == "replay_pack_v1:2025:15:R"
    assert _pack_cache_key(2025, 15, "r") == _pack_cache_key(2025, 15, "R")
    key = synthetic_session_key(2025, 15, "R")
    assert replay_pack_disk_key(key) == _pack_cache_key(2025, 15, "R")
    assert replay_pack_disk_key(key, 2025, 15, "R") == _pack_cache_key(2025, 15, "R")


def test_stub_pack_hydrates_from_disk():
    from backend.cache import get_disk
    from backend.live import (
        _REPLAY_PACKS,
        hydrate_replay_pack_cache,
        replay_pack_disk_key,
        save_replay_pack_disk,
        synthetic_session_key,
    )

    key = synthetic_session_key(2024, 22, "R")
    cache_key = replay_pack_disk_key(key, 2024, 22, "R")
    disk = get_disk()
    disk.pop(cache_key, default=None)
    _REPLAY_PACKS.pop(key, None)
    pack = {
        "laps": [{"driver_number": 1, "lap_number": 1, "lap_duration": 90.0}],
        "date_end": datetime(2024, 12, 1, 15, 0, tzinfo=timezone.utc),
        "year": 2024,
        "round_number": 22,
        "session_type": "R",
        "session_status": "COMPLETED",
        "stage": "minimal",
        "source": "fastf1",
        "ff1": {},
    }
    assert save_replay_pack_disk(key, pack) is True
    _REPLAY_PACKS[key] = {
        "year": 2024,
        "round_number": 22,
        "laps": [],
        "stage": "metadata",
        "source": "fastf1",
    }
    loaded, memory_hit, disk_hit = hydrate_replay_pack_cache(key, 2024, 22, "R")
    assert memory_hit is False
    assert disk_hit is True
    assert loaded is not None
    assert loaded["laps"][0]["lap_number"] == 1
    disk.pop(cache_key, default=None)
    _REPLAY_PACKS.pop(key, None)


def test_ff1_clock_bounds_without_telemetry():
    from datetime import datetime, timezone

    from backend.sessions import _ff1_clock_bounds

    class _Sess:
        @property
        def t0_date(self):
            raise RuntimeError("The data you are trying to access has not been loaded yet")

    start = datetime(2025, 8, 31, 13, 0, tzinfo=timezone.utc)
    t0, t1 = _ff1_clock_bounds(
        _Sess(),
        [{"date_start": start.isoformat(), "lap_duration": 90.0}],
        {},
        None,
        None,
    )
    assert t0 == start
    assert t1 is not None
    assert abs((t1 - t0).total_seconds() - 90) < 0.01


def test_history_ttl_keeps_current_season_shorter():
    from backend.main import _history_ttl
    from backend.cache import TTL_COMPLETED, TTL_SESSION

    assert _history_ttl(2024) == TTL_COMPLETED
    assert _history_ttl(2026) == TTL_SESSION


def test_zandvoort_2026_notes_include_hadjar():
    from backend.calendar import get_round

    rnd = get_round(2026, 15, as_of=datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc))
    blob = " ".join(rnd.notes).lower()
    assert "hadjar" in blob
    assert rnd.circuit_key == "netherlands"


def test_sq_live_window_at_zandvoort_2026():
    as_of = datetime(2026, 8, 21, 15, 2, tzinfo=timezone.utc)
    weekend = get_round_sessions(2026, 15, as_of=as_of)
    by = {s.session_type: s.status for s in weekend.sessions}
    assert by["FP1"] == "COMPLETED"
    assert by["SQ"] == "LIVE"
    assert by["S"] == "UPCOMING"
    assert by["Q"] == "UPCOMING"
    assert by["R"] == "UPCOMING"


def test_sq_duration_covers_chequered_not_overnight():
    start = datetime(2026, 8, 21, 14, 30, tzinfo=timezone.utc)
    assert _session_status(start, datetime(2026, 8, 21, 15, 2, tzinfo=timezone.utc), 0.8) == "LIVE"
    assert _session_status(start, datetime(2026, 8, 21, 15, 40, tzinfo=timezone.utc), 0.8) == "COMPLETED"


def test_after_sq_next_is_sprint():
    as_of = datetime(2026, 8, 21, 15, 40, tzinfo=timezone.utc)
    weekend = get_round_sessions(2026, 15, as_of=as_of)
    by = {s.session_type: s.status for s in weekend.sessions}
    assert by["FP1"] == "COMPLETED"
    assert by["SQ"] == "COMPLETED"
    assert by["S"] == "UPCOMING"
    assert by["Q"] == "UPCOMING"
    assert by["R"] == "UPCOMING"


def test_zandvoort_race_is_open_before_lights():
    from backend.calendar import session_is_open

    as_of = datetime(2026, 8, 23, 12, 20, tzinfo=timezone.utc)
    assert session_is_open(2026, 15, "R", as_of=as_of) is True
    assert session_is_open(2025, 15, "R", as_of=as_of) is False


def test_open_race_does_not_load_fastf1_laps(monkeypatch):
    monkeypatch.setattr("backend.calendar.session_is_open", lambda *_a, **_k: True)
    from backend.sessions import session_laps

    out = session_laps(2026, 15, "R")
    assert out.laps == []
    assert out.session_type == "R"


def test_after_zandvoort_race_next_is_monza():
    from backend.calendar import get_calendar, next_race

    as_of = datetime(2026, 8, 23, 16, 0, tzinfo=timezone.utc)
    cal = get_calendar(2026, as_of=as_of)
    nl = next(r for r in cal.rounds if r.round_number == 15)
    assert nl.status == "COMPLETED"
    nxt = next_race(as_of=as_of)
    assert nxt.round_number == 16
    assert "ital" in (nxt.name or "").lower() or "monza" in (nxt.circuit_name or "").lower()


def test_imola_2026_is_cancelled():
    from backend.calendar import _SCHED_MEM, get_calendar

    _SCHED_MEM.pop(2026, None)
    cal = get_calendar(2026, as_of=datetime(2026, 9, 3, 12, 0, tzinfo=UTC))
    imola = next(r for r in cal.rounds if r.round_number == 7)
    assert imola.status == "CANCELLED"


def test_calendar_2026_race_morning_uses_overlay():
    from backend.calendar import _SCHED_MEM, get_calendar, next_race

    _SCHED_MEM.pop(2026, None)
    as_of = datetime(2026, 8, 23, 11, 0, tzinfo=timezone.utc)
    cal = get_calendar(2026, as_of=as_of)
    nl = next(r for r in cal.rounds if r.round_number == 15)
    assert nl.status == "LIVE"
    assert nl.circuit_key == "netherlands"
    nxt = next_race(as_of=as_of)
    assert nxt.round_number == 15
    assert nxt.next_session_name in {"Race", "R"} or (nxt.next_session_name or "").upper().startswith("R")


def test_chequered_closes_live_window():
    from backend.live import _STATE, _session_window_live

    _STATE["race_control"] = [{"flag": "CHEQUERED", "date": "2026-08-22T10:32:00+00:00"}]
    sess = {
        "date_start": "2026-08-22T10:00:00+00:00",
        "date_end": "2026-08-22T11:00:00+00:00",
    }
    still = datetime(2026, 8, 22, 10, 33, tzinfo=timezone.utc)
    done = datetime(2026, 8, 22, 10, 35, tzinfo=timezone.utc)
    assert _session_window_live(sess, still) is True
    assert _session_window_live(sess, done) is False
    _STATE["race_control"] = []


def test_session_window_opens_20_min_before_sprint():
    sess = {
        "date_start": "2026-08-22T10:00:00+00:00",
        "date_end": "2026-08-22T11:00:00+00:00",
    }
    early = datetime(2026, 8, 22, 9, 42, tzinfo=timezone.utc)
    too_early = datetime(2026, 8, 22, 9, 35, tzinfo=timezone.utc)
    assert _session_window_live(sess, early) is True
    assert _session_window_live(sess, too_early) is False


def test_session_window_ends_after_short_grace():
    sess = {
        "date_start": "2026-08-21T14:30:00+00:00",
        "date_end": "2026-08-21T15:14:00+00:00",
    }
    live_at = datetime(2026, 8, 21, 15, 16, tzinfo=timezone.utc)
    done_at = datetime(2026, 8, 21, 15, 30, tzinfo=timezone.utc)
    assert _session_window_live(sess, live_at) is True
    assert _session_window_live(sess, done_at) is False


def test_session_type_map_sprint_qualifying():
    assert _session_type_map("Sprint Qualifying", "Qualifying") == "SQ"
    assert _session_type_map("Qualifying", "Qualifying") == "Q"
    assert _session_type_map("Sprint", "Race") == "S"
    assert _session_type_map("Race", "Race") == "R"


def test_unique_positions_dedupe():
    from backend.live import _unique_positions

    out = _unique_positions({1: 1, 44: 1, 16: 3, 81: 2})
    assert sorted(out.values()) == [1, 2, 3, 4]
    assert len(set(out.values())) == 4


def test_sector_tone_from_times():
    from backend.live import _sector_tone

    assert _sector_tone(22100, 22100, 22100, None) == "purple"
    assert _sector_tone(22400, 22400, 22100, None) == "green"
    assert _sector_tone(23000, 22400, 22100, None) == "yellow"
    assert _sector_tone(23000, 22400, 22100, [2048]) == "yellow"
    assert _sector_tone(22100, 22400, 22100, [2051]) == "purple"


def test_sector_colours_from_openf1_segments():
    assert _sector_colour_from_segments([2049, 2051]) == "purple"
    assert _sector_colour_from_segments([2049, 2049]) == "green"
    assert _sector_colour_from_segments([2048]) == "yellow"
    assert _sector_colour_from_segments([]) == "grey"


def test_replay_clock_filters_laps_and_weather():
    from backend.live import _laps_upto, _weather_at

    as_of = datetime(2026, 8, 21, 10, 45, tzinfo=timezone.utc)
    laps = [
        {"driver_number": 1, "date_start": "2026-08-21T10:31:00+00:00", "lap_duration": 72.1, "lap_number": 1},
        {"driver_number": 1, "date_start": "2026-08-21T10:50:00+00:00", "lap_duration": 71.4, "lap_number": 2},
    ]
    kept = _laps_upto(laps, as_of)
    assert len(kept) == 1
    assert kept[0]["lap_number"] == 1
    weather = [
        {"date": "2026-08-21T10:30:00+00:00", "air_temperature": 18.0, "track_temperature": 28.0},
        {"date": "2026-08-21T10:40:00+00:00", "air_temperature": 19.5, "track_temperature": 31.0},
        {"date": "2026-08-21T11:00:00+00:00", "air_temperature": 21.0, "track_temperature": 35.0},
    ]
    row = _weather_at(weather, as_of)
    assert row["air_temperature"] == 19.5
    assert row["track_temperature"] == 31.0


def test_best_lap_ignores_unfinished():
    from backend.live import _best_ms_from_laps

    as_of = datetime(2026, 8, 21, 10, 32, tzinfo=timezone.utc)
    laps = [
        {
            "driver_number": 44,
            "date_start": "2026-08-21T10:31:00+00:00",
            "lap_duration": 90.0,
            "lap_number": 1,
        }
    ]
    assert _best_ms_from_laps(laps, as_of) == {}
    later = datetime(2026, 8, 21, 10, 33, tzinfo=timezone.utc)
    assert _best_ms_from_laps(laps, later)[44] == 90_000


def test_openf1_url_keeps_date_operator():
    url = openf1_url("location", {"session_key": "latest", "date>": "2026-08-21T15:00:00"})
    assert "date>" in url
    assert "session_key=latest" in url


def test_close_circuit_loop_fills_start_finish_gap():
    from backend.sessions import close_circuit_loop, pit_lane_from_path

    xs = [0.0, 10.0, 10.0, 0.0]
    ys = [0.0, 0.0, 10.0, 10.2]
    cx, cy = close_circuit_loop(xs, ys)
    assert cx[0] == cx[-1]
    assert abs(cy[0] - cy[-1]) < 1e-9
    pit_x, pit_y, stalls = pit_lane_from_path(cx, cy, stalls=5)
    assert len(pit_x) >= 2
    assert len(stalls) == 5


def test_close_circuit_loop_trims_large_jump():
    from backend.sessions import close_circuit_loop

    xs = [0.0, 8.0, 8.0, 0.2, 80.0]
    ys = [0.0, 0.0, 8.0, 0.2, 80.0]
    cx, cy = close_circuit_loop(xs, ys)
    gap = ((cx[0] - cx[-1]) ** 2 + (cy[0] - cy[-1]) ** 2) ** 0.5
    assert gap < 1.0
    assert max(cx) < 20


def test_quali_windows_are_fia_segments_not_session_envelope():
    from backend.sessions import official_quali_windows, _quali_windows_from_duration

    sprint = _quali_windows_from_duration(2400, True)
    assert [w["id"] for w in sprint] == ["SQ1", "SQ2", "SQ3"]
    assert sprint[0]["end_s"] - sprint[0]["start_s"] == 12 * 60
    assert sprint[1]["end_s"] - sprint[1]["start_s"] == 10 * 60
    assert sprint[2]["end_s"] - sprint[2]["start_s"] == 8 * 60
    assert sprint[-1]["end_s"] < 2400

    q = official_quali_windows(False)
    assert [w["id"] for w in q] == ["Q1", "Q2", "Q3"]
    assert q[0]["end_s"] - q[0]["start_s"] == 18 * 60
    assert q[1]["end_s"] - q[1]["start_s"] == 15 * 60
    assert q[2]["end_s"] - q[2]["start_s"] == 12 * 60
    stretched = _quali_windows_from_duration(90 * 60, False)
    assert stretched[-1]["end_s"] - stretched[-1]["start_s"] == 12 * 60


def test_quali_windows_and_reasons():
    from backend.live import _driver_reason, _quali_phase
    from backend.sessions import _quali_windows_from_duration

    wins = _quali_windows_from_duration(3600, False)
    assert [w["id"] for w in wins] == ["Q1", "Q2", "Q3"]
    assert _quali_phase(wins, 60) == "Q1"
    assert _driver_reason(
        code="ALO",
        has_sample=False,
        in_pit=False,
        eliminated=False,
        status="",
        phase="Q1",
        q_times=None,
        started=False,
    ) == "Not started"
    assert _driver_reason(
        code="ALO",
        has_sample=True,
        in_pit=False,
        eliminated=False,
        status="Did not start",
        phase="Q1",
        q_times=None,
        started=False,
    ) == "DNS"
    assert _driver_reason(
        code="ALO",
        has_sample=True,
        in_pit=False,
        eliminated=True,
        status="",
        phase="Q2",
        q_times={"q1_ms": 90000, "q2_ms": None, "q3_ms": None},
        started=True,
    ) == "OUT Q1"


def test_ff1_position_sample():
    from backend.sessions import sample_ff1_position

    samples = [(100.0, 1.0, 2.0, "OnTrack"), (110.0, 3.0, 4.0, "OnTrack")]
    assert sample_ff1_position(samples, 99.0) is None
    hit = sample_ff1_position(samples, 105.0)
    assert hit is not None
    assert abs(hit[0] - 2.0) < 1e-6
    assert abs(hit[1] - 3.0) < 1e-6
    assert hit[2] == "OnTrack"
    later = sample_ff1_position(samples, 200.0)
    assert later == (3.0, 4.0, "OnTrack")


def test_race_start_uses_lap_one_when_no_green_flag():
    from backend.live import _race_start_s

    start = datetime(2026, 8, 23, 13, 0, tzinfo=timezone.utc)
    pack = {
        "green_flag_s": None,
        "date_start": start,
        "laps": [
            {"driver_number": 1, "lap_number": 1, "date_start": "2026-08-23T13:24:00+00:00"},
            {"driver_number": 2, "lap_number": 1, "date_start": "2026-08-23T13:24:10+00:00"},
        ],
    }
    assert _race_start_s(pack) == 24 * 60


def test_status_is_pit_accepts_fastf1_labels():
    from backend.sessions import status_is_pit

    assert status_is_pit("PitLane")
    assert status_is_pit("InPit")
    assert status_is_pit("in_pit")
    assert status_is_pit("Pit")
    assert not status_is_pit("OnTrack")
    assert not status_is_pit("OffTrack")


def test_pit_lane_from_points_follows_gps():
    from backend.sessions import pit_lane_from_points, pit_lane_from_samples

    path_x = [float(i) for i in range(40)]
    path_y = [0.0] * 40
    pts = [(float(i), 18.0) for i in range(2, 18)]
    lane = pit_lane_from_points(pts, path_x, path_y)
    assert lane is not None
    pit_x, pit_y, stalls = lane
    assert len(pit_x) >= 8
    assert all(y > 10 for y in pit_y)
    assert len(stalls) >= 8
    samples = {
        "VER": [(100.0 + i, float(i + 2), 18.0, "PitLane") for i in range(16)],
        "NOR": [(200.0 + i, 10.0, 0.0, "OnTrack") for i in range(8)],
    }
    from_samples = pit_lane_from_samples(samples, path_x, path_y)
    assert from_samples is not None
    assert len(from_samples[0]) >= 8


def test_replay_adds_drs_when_other_markers_exist():
    from backend.live import _as_markers
    from backend.models import CircuitMarker
    from backend.sessions import drs_on_path

    existing = _as_markers([{"kind": "sf", "x": 10, "y": 10, "label": "S/F"}])
    assert [m.kind for m in existing] == ["sf"]
    xs = [float(i) for i in range(40)]
    ys = [0.0] * 20 + [float(i) for i in range(20)]
    segs, marks = drs_on_path(xs, ys, "netherlands")
    assert segs
    assert any(m.kind == "drs_detect" for m in marks)
    merged = existing + list(marks)
    assert any(m.kind == "drs_detect" for m in merged)
    assert isinstance(marks[0], CircuitMarker)


def test_session_flag_tracks_safety_car():
    from backend.live import _flag_from_rc

    rc = [
        {"flag": "GREEN", "message": "LIGHTS OUT"},
        {"flag": "SC", "category": "SafetyCar", "message": "SAFETY CAR DEPLOYED"},
    ]
    assert _flag_from_rc(rc) == "SC"
    rc.append({"flag": "GREEN", "message": "TRACK CLEAR"})
    assert _flag_from_rc(rc) == "GREEN"


def test_flag_from_rc_reads_yellow_and_red():
    from backend.live import _flag_from_rc

    assert _flag_from_rc([{"flag": "YELLOW", "message": "YELLOW FLAG - TURN 8"}]) == "YELLOW"
    assert _flag_from_rc([{"flag": "RED", "message": "RED FLAG"}]) == "RED"
    assert _flag_from_rc([{"flag": "YELLOW", "message": "CRASH"}, {"flag": "GREEN", "message": "TRACK CLEAR"}]) == "GREEN"
    assert (
        _flag_from_rc(
            [
                {"flag": "RED", "message": "RED FLAG - RACE SUSPENDED"},
                {"flag": "GREEN", "message": "TRACK CLEAR"},
                {"flag": "YELLOW", "message": "YELLOW FLAG - SECTOR 7"},
                {"message": "TURN 14 INCIDENT NOTED - YELLOW FLAG INFRINGEMENT"},
            ]
        )
        == "YELLOW"
    )
    assert (
        _flag_from_rc(
            [
                {"flag": "YELLOW", "message": "YELLOW IN TRACK SECTOR 3"},
                {"flag": "CLEAR", "message": "CLEAR IN TRACK SECTOR 3"},
                {"message": "FIA STEWARDS: DRIVE THROUGH PENALTY FOR CAR 41 (LIN) - YELLOW FLAG INFRINGEMENT"},
            ]
        )
        == "GREEN"
    )
    assert (
        _flag_from_rc(
            [
                {"flag": "YELLOW", "message": "YELLOW IN TRACK SECTOR 10"},
                {"flag": "YELLOW", "message": "YELLOW IN TRACK SECTOR 3"},
                {"flag": "CLEAR", "message": "CLEAR IN TRACK SECTOR 3"},
            ]
        )
        == "YELLOW"
    )


def test_gps_usable_rejects_origin_and_stale():
    from datetime import datetime, timedelta, timezone

    from backend.live import _circ_delta, _circ_mean_frac, _gps_usable

    now = datetime(2026, 8, 23, 13, 34, tzinfo=timezone.utc)
    assert not _gps_usable({"x": 0, "y": 0, "date": now.isoformat()})
    assert _gps_usable({"x": 1788, "y": 4309, "date": now.isoformat()}, now=now)
    old = (now - timedelta(seconds=40)).isoformat()
    assert not _gps_usable({"x": 1788, "y": 4309, "date": old}, now=now)
    mean = _circ_mean_frac([0.99, 0.00, 0.01, 0.02, 0.03])
    assert mean is not None
    assert abs(_circ_delta(mean, 0.01)) < 0.04
    assert abs(_circ_delta(0.123, 0.02)) > 0.06


def test_inactive_from_laps_marks_dnf():
    from backend.live import _inactive_from_laps

    codes = {1: "VER", 44: "HAM", 16: "LEC"}
    laps = [
        {"driver_number": 44, "lap_number": 5, "lap_duration": 75.1},
        {"driver_number": 16, "lap_number": 5, "lap_duration": 75.4},
        {"driver_number": 1, "lap_number": 1, "lap_duration": None},
    ]
    assert _inactive_from_laps(laps, codes) == {"VER"}
    midfield = [
        {"driver_number": 44, "lap_number": 12, "lap_duration": 80.0},
        {"driver_number": 16, "lap_number": 11, "lap_duration": 80.0},
        {"driver_number": 41, "lap_number": 10, "lap_duration": 80.0},
    ]
    assert _inactive_from_laps(midfield, {44: "HAM", 16: "LEC", 41: "LIN"}) == set()


def test_ff1_car_sample():
    from backend.sessions import sample_ff1_car

    samples = [(100.0, 80.0, 0.0, 250.0, 0.0), (110.0, 12.0, 90.0, 80.0, 12.0)]
    assert sample_ff1_car(samples, 99.0) is None
    hit = sample_ff1_car(samples, 105.0)
    assert hit is not None
    assert abs(hit[0] - 46.0) < 1e-6
    assert abs(hit[1] - 45.0) < 1e-6
    assert abs(hit[2] - 165.0) < 1e-6
    later = sample_ff1_car(samples, 200.0)
    assert later == (12.0, 90.0, 80.0, 12.0)


def test_replay_timing_rows_use_clock_car_data():
    from backend.live import _timing_rows_from_payload

    as_of = datetime(2026, 8, 23, 14, 12, tzinfo=timezone.utc)
    rows = _timing_rows_from_payload(
        codes={1: "VER"},
        colours={1: "#3671C6"},
        positions={1: 1},
        laps=[{"driver_number": 1, "lap_number": 4, "lap_duration": 72.1}],
        stints=[],
        intervals={},
        eliminated=set(),
        locations={},
        as_of=as_of,
        cars={1: {"throttle": 88, "brake": 14, "speed": 277, "drs": 12}},
    )
    assert rows[0].driver_code == "VER"
    assert rows[0].throttle_pct == 88
    assert rows[0].brake_pct == 14
    assert rows[0].speed_kph == 277
    assert rows[0].drs_open is True


def test_replay_timing_rows_ignore_live_car_state():
    from backend.live import _STATE, _timing_rows_from_payload

    as_of = datetime(2026, 8, 23, 14, 12, tzinfo=timezone.utc)
    _STATE["car_data"] = {1: {"throttle": 99, "brake": 0, "speed": 300, "drs": 14}}
    try:
        rows = _timing_rows_from_payload(
            codes={1: "VER"},
            colours={},
            positions={1: 1},
            laps=[{"driver_number": 1, "lap_number": 2, "lap_duration": 73.0}],
            stints=[],
            intervals={},
            eliminated=set(),
            locations={},
            as_of=as_of,
        )
        assert rows[0].throttle_pct is None
        assert rows[0].brake_pct is None
    finally:
        _STATE["car_data"] = {}


def test_cars_from_samples_at_clock():
    from backend.live import _cars_from_samples

    clock = datetime(2026, 8, 23, 14, 0, 10, tzinfo=timezone.utc)
    t0 = datetime(2026, 8, 23, 14, 0, 0, tzinfo=timezone.utc).timestamp()
    pack = {
        "codes": {1: "VER"},
        "ff1": {
            "num_by_code": {"VER": 1},
            "car_samples": {"VER": [(t0, 10.0, 0.0, 80.0, 0.0), (t0 + 8, 95.0, 0.0, 290.0, 12.0)]},
        },
    }
    cars = _cars_from_samples(pack, clock)
    assert cars[1]["throttle"] == 95.0
    assert cars[1]["speed"] == 290.0
    assert cars[1]["drs"] == 12.0


def test_pit_lane_has_entry_exit_and_stalls():
    from backend.sessions import pit_lane_from_path, point_on_path

    xs = [float(i) for i in range(40)]
    ys = [0.0] * 20 + [float(i) for i in range(20)]
    pit_x, pit_y, stalls = pit_lane_from_path(xs, ys, stalls=8)
    assert len(pit_x) >= 4
    assert len(stalls) == 8
    x, y = point_on_path(pit_x, pit_y, 0.5)
    assert isinstance(x, float) and isinstance(y, float)


def test_grid_slots_are_staggered():
    from backend.sessions import grid_slot_xy

    xs = [float(i) for i in range(50)]
    ys = [10.0] * 50
    p1 = grid_slot_xy(xs, ys, 1)
    p2 = grid_slot_xy(xs, ys, 2)
    p3 = grid_slot_xy(xs, ys, 3)
    assert (p1[0], p1[1]) != (p2[0], p2[1])
    assert p1[2] > p3[2] or abs(p1[2] - p3[2]) > 0


def test_jolpica_keeps_limit_query(monkeypatch):
    from backend import http_client

    seen: dict[str, str] = {}
    monkeypatch.setattr(http_client, "get_json", lambda url: seen.setdefault("url", url) or {})
    http_client.jolpica("circuits/zandvoort/results.json?limit=200")
    assert seen["url"].endswith("results.json?limit=200")
    assert "200.json" not in seen["url"]


def test_s_f_flyby_is_not_a_pit():
    from backend.live import _location_in_pit

    path_x = [0.0, 40.0, 40.0, 0.0, 0.0]
    path_y = [0.0, 0.0, 20.0, 20.0, 0.0]
    pit_x = [2.0, 12.0, 12.0]
    pit_y = [6.0, 6.0, 10.0]
    assert _location_in_pit(5.0, 0.2, "OnTrack", path_x, path_y, pit_x, pit_y) is False
    assert _location_in_pit(12.0, 6.1, "Pit", path_x, path_y, pit_x, pit_y) is True


def test_peek_circuit_history_does_not_fetch():
    from backend.analytics import peek_circuit_history

    assert peek_circuit_history("circuit_that_does_not_exist_xyz") is None


def test_rainfall_from_samples_uses_recent_openf1_values():
    from backend.live import rainfall_flag, rainfall_from_samples

    assert rainfall_flag(1) is True
    assert rainfall_flag(0) is False
    assert rainfall_flag(True) is True
    assert rainfall_flag("false") is False
    dry = [{"rainfall": 0}, {"rainfall": 0}, {"rainfall": 0}, {"rainfall": 0}, {"rainfall": 0}]
    wet = [{"rainfall": 0}, {"rainfall": 0}, {"rainfall": 0}, {"rainfall": 0}, {"rainfall": 1}]
    assert rainfall_from_samples(dry) is False
    assert rainfall_from_samples(wet) is True
    assert rainfall_from_samples([]) is False


def test_tower_tyre_life_uses_lap_row_not_stint_start_age():
    from backend.live import _timing_rows_from_payload

    rows = _timing_rows_from_payload(
        codes={1: "VER"},
        colours={},
        positions={1: 1},
        laps=[{"driver_number": 1, "lap_number": 15, "lap_duration": 74.0, "tyre_life": 15}],
        stints=[
            {
                "driver_number": 1,
                "stint_number": 1,
                "lap_start": 1,
                "tyre_age_at_start": 1,
                "compound": "MEDIUM",
            }
        ],
        intervals={},
        eliminated=set(),
        locations={},
    )
    assert rows[0].driver_code == "VER"
    assert rows[0].tyre_life == 15


def test_tower_tyre_life_falls_back_to_stint_age_plus_laps_and_resets_after_pit():
    from backend.live import _timing_rows_from_payload

    stints = [
        {
            "driver_number": 1,
            "stint_number": 1,
            "lap_start": 1,
            "tyre_age_at_start": 1,
            "compound": "MEDIUM",
        },
        {
            "driver_number": 1,
            "stint_number": 2,
            "lap_start": 16,
            "tyre_age_at_start": 1,
            "compound": "HARD",
        },
    ]
    before = _timing_rows_from_payload(
        codes={1: "VER"},
        colours={},
        positions={1: 1},
        laps=[{"driver_number": 1, "lap_number": 15, "lap_duration": 74.0}],
        stints=stints,
        intervals={},
        eliminated=set(),
        locations={},
    )
    assert before[0].tyre_life == 15
    after = _timing_rows_from_payload(
        codes={1: "VER"},
        colours={},
        positions={1: 1},
        laps=[{"driver_number": 1, "lap_number": 16, "lap_duration": 94.0}],
        stints=stints,
        intervals={},
        eliminated=set(),
        locations={},
    )
    assert after[0].tyre_life == 1
    assert after[0].stint_number == 2
