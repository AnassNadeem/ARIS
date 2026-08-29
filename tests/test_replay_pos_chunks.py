"""10-lap position chunks — never keep a full-race GPS object in the pack."""

from __future__ import annotations

import inspect

from backend.sessions import (
    POS_CHUNK_LAPS,
    _pack_cache_key,
    iter_pos_chunk_ranges,
    pos_chunk_cache_key,
    pos_chunk_range_for_lap,
    pos_chunk_time_window,
    slice_pos_samples,
)


def test_pos_chunk_key_matches_spec():
    assert pos_chunk_cache_key(2025, 15, "R", 0, 10) == "replay_pack_v1:2025:15:R:pos:0-10"
    assert pos_chunk_cache_key(2025, 15, "R", 10, 20) == "replay_pack_v1:2025:15:R:pos:10-20"
    assert pos_chunk_cache_key(2025, 15, "R", 0, 10).startswith(_pack_cache_key(2025, 15, "R"))


def test_pos_chunk_range_for_lap():
    assert POS_CHUNK_LAPS == 10
    assert pos_chunk_range_for_lap(1) == (0, 10)
    assert pos_chunk_range_for_lap(10) == (0, 10)
    assert pos_chunk_range_for_lap(11) == (10, 20)
    assert pos_chunk_range_for_lap(72) == (70, 80)


def test_iter_pos_chunk_ranges_covers_race():
    ranges = iter_pos_chunk_ranges(72)
    assert ranges[0] == (0, 10)
    assert ranges[-1] == (70, 80)
    assert (10, 20) in ranges


def test_slice_pos_samples_by_time_window():
    samples = {
        "VER": [
            (100.0, 0.0, 0.0, "OnTrack"),
            (110.0, 1.0, 0.0, "OnTrack"),
            (200.0, 2.0, 0.0, "OnTrack"),
        ]
    }
    starts = {1: 100.0, 11: 200.0}
    t0, t1 = pos_chunk_time_window(starts, 0, 10)
    assert t0 is None
    assert t1 == 200.0
    first = slice_pos_samples(samples, t0, t1)
    assert [row[0] for row in first["VER"]] == [100.0, 110.0]


def test_build_ff1_replay_assets_never_loads_car_or_full_telemetry():
    from backend.sessions import build_ff1_replay_assets

    src = inspect.getsource(build_ff1_replay_assets)
    assert "telemetry=False" in src
    assert "telemetry=telemetry" not in src
    assert "car_data" not in src
    assert "parse_and_chunk_position_data" in src


def test_http_replay_helpers_wait_for_minimal_not_full_gps():
    from backend import live as live_mod

    for name in ("live_laps", "live_telemetry", "live_race_control", "live_stints", "live_weather"):
        src = inspect.getsource(getattr(live_mod, name))
        assert 'wait_for="minimal"' in src, name
        assert 'wait_for="full"' not in src, name


def test_pack_status_peek_does_not_await_fastf1_upgrade():
    from backend.live import peek_replay_pack_status, peek_replay_pos_chunk

    src = inspect.getsource(peek_replay_pack_status)
    assert "_kick_pack_job" in src
    assert "await _upgrade_pack_fastf1" not in src
    assert "await _fill_gps_chunks" not in src
    chunk_src = inspect.getsource(peek_replay_pos_chunk)
    assert "load_session" not in chunk_src
    assert "position_data" not in chunk_src
    assert "car_data" not in chunk_src


def test_ensure_pos_chunk_swaps_window_from_disk(monkeypatch):
    from backend import live as live_mod

    stored = {
        (2025, 15, "R", 10, 20): {"VER": [(50.0, 1.0, 2.0, "OnTrack")]},
    }

    monkeypatch.setattr(
        "backend.sessions.load_pos_chunk_disk",
        lambda year, rnd, stype, lo, hi: stored.get((year, rnd, stype, lo, hi)),
    )

    pack = {
        "year": 2025,
        "round_number": 15,
        "session_type": "R",
        "source": "fastf1",
        "path_x": [0.0, 1.0],
        "path_y": [0.0, 1.0],
        "pos_chunks": [{"lo": 0, "hi": 10}, {"lo": 10, "hi": 20}],
        "pos_chunk_loaded": {"lo": 0, "hi": 10},
        "ff1": {
            "pos_samples": {"VER": [(1.0, 0.0, 0.0, "OnTrack")]},
            "pos_chunk_loaded": {"lo": 0, "hi": 10},
            "synthetic_gps": False,
        },
    }
    live_mod.ensure_replay_pos_chunk(pack, 11)
    assert pack["pos_chunk_loaded"] == {"lo": 10, "hi": 20}
    assert pack["ff1"]["pos_samples"]["VER"][0][0] == 50.0


def test_prewarm_round_pack_does_not_wait_for_full_gps():
    from backend.main import _prewarm_round_pack

    src = inspect.getsource(_prewarm_round_pack)
    assert 'wait_for="minimal"' in src
    assert 'wait_for="full"' not in src
