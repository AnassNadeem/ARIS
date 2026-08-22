"""Live session calendar windows and OpenF1 helper parsing — no network."""

from datetime import datetime, timezone

from backend.cache import TTL_NEXT_RACE
from backend.calendar import _session_status, get_round_sessions
from backend.http_client import openf1_url
from backend.live import _sector_colour_from_segments, _session_type_map, _session_window_live


def test_ttl_next_race_is_short():
    assert TTL_NEXT_RACE <= 30


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
    assert hit == (1.0, 2.0, "OnTrack")
    later = sample_ff1_position(samples, 200.0)
    assert later == (3.0, 4.0, "OnTrack")
