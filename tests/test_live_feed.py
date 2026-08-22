"""Live dashboard parsers and calendar windows — no live network required."""

from datetime import datetime, timezone

from aris.live_feed import (
    LiveSnapshot,
    build_live_race_state,
    compound_letter,
    delay_note,
    fmt_gap,
    fmt_ms,
    just_ended_window,
    last_stint,
    matching_window,
    next_window,
    parse_timing_lines,
    session_type_map,
    weather_from_topic,
)
from backend.f1_live import _ingest_cardata, cardata, parse_laptime_ms, sector_colour


def test_session_type_map_sprint_weekend():
    assert session_type_map("Sprint Qualifying", "Qualifying") == "SQ"
    assert session_type_map("Sprint", "Race") == "S"
    assert session_type_map("Race", "Race") == "R"
    assert session_type_map("Practice 1") == "FP1"


def test_compound_letter_from_feed_strings():
    assert compound_letter("SOFT") == "S"
    assert compound_letter("medium") == "M"
    assert compound_letter("HYPERSOFT") is None or compound_letter("HYPERSOFT") == "H"
    assert compound_letter("intermediate") == "I"
    assert compound_letter("WET") == "W"


def test_last_stint_accepts_dict_or_list():
    keyed = {"0": {"Compound": "SOFT", "TotalLaps": 3}, "1": {"Compound": "MEDIUM", "TotalLaps": 8}}
    stint, n = last_stint(keyed)
    assert n == 2
    assert stint["Compound"] == "MEDIUM"
    listed, n2 = last_stint([{"Compound": "HARD", "TotalLaps": 12}])
    assert n2 == 1
    assert listed["Compound"] == "HARD"
    assert last_stint(None) == ({}, 0)


def test_fmt_helpers():
    assert fmt_ms(92608) == "1:32.608"
    assert fmt_ms(71234) == "1:11.234"
    assert fmt_ms(None) == "—"
    assert fmt_gap(0) == "LEADER"
    assert fmt_gap(1.234) == "+1.234"
    assert fmt_gap(None) == "—"


def test_weather_and_sector_colour():
    wx = weather_from_topic({"AirTemp": "19.5", "TrackTemp": "31", "Rainfall": "0"})
    assert wx["air_temp"] == 19.5
    assert wx["track_temp"] == 31.0
    assert wx["rainfall"] is False
    assert sector_colour({"Value": "23.1", "OverallFastest": True}) == "purple"
    assert sector_colour({"Value": "23.4", "PersonalFastest": True}) == "green"
    assert sector_colour({}) == "grey"


def test_parse_timing_lines_real_shape():
    timing = {
        "Lines": {
            "1": {
                "Position": "1",
                "Tla": "VER",
                "GapToLeader": "",
                "IntervalToPositionAhead": {"Value": ""},
                "LastLapTime": {"Value": "1:12.345"},
                "BestLapTime": {"Value": "1:11.900"},
                "Sectors": {
                    "0": {"Value": "23.100", "OverallFastest": True},
                    "1": {"Value": "24.200", "PersonalFastest": True},
                    "2": {"Value": "24.045"},
                },
                "NumberOfLaps": 8,
                "GridPos": "3",
                "InPit": False,
            },
            "44": {
                "Position": "2",
                "Tla": "HAM",
                "GapToLeader": "+1.842",
                "IntervalToPositionAhead": {"Value": "+1.842"},
                "LastLapTime": {"Value": "1:12.800"},
                "BestLapTime": {"Value": "1:12.100"},
                "Sectors": [
                    {"Value": "23.400"},
                    {"Value": "24.500"},
                    {"Value": "24.900"},
                ],
                "NumberOfLaps": 8,
                "GridPos": "1",
            },
        }
    }
    app = {
        "Lines": {
            "1": {"Stints": {"0": {"Compound": "SOFT", "TotalLaps": 8}}},
            "44": {"Stints": [{"Compound": "MEDIUM", "TotalLaps": 8}]},
        }
    }
    drivers = {
        "1": {"Tla": "VER", "FullName": "Max VERSTAPPEN", "TeamName": "Red Bull", "TeamColour": "3671C6"},
        "44": {"Tla": "HAM", "FullName": "Lewis HAMILTON", "TeamName": "Ferrari", "TeamColour": "E8002D"},
    }
    rows = parse_timing_lines(
        timing,
        drivers=drivers,
        app=app,
        positions={"1": {"X": 100.0, "Y": 200.0, "Status": "OnTrack"}},
        cardata={"1": {"throttle": 98, "brake": 0, "speed": 288, "rpm": 11100, "gear": 8}},
    )
    assert [r.code for r in rows] == ["VER", "HAM"]
    assert rows[0].position == 1
    assert rows[0].position_change == 2
    assert rows[0].compound == "S"
    assert rows[0].tyre_life == 8
    assert rows[0].fastest_lap is True
    assert rows[0].gps_x == 100.0
    assert rows[0].throttle == 98
    assert rows[0].team_colour == "#3671C6"
    assert rows[1].position_change == -1
    assert rows[1].compound == "M"
    assert parse_laptime_ms(timing["Lines"]["1"]["LastLapTime"]) == 72345


def test_cardata_ingest_keeps_latest_channels():
    _ingest_cardata(
        {
            "Entries": [
                {
                    "Cars": {
                        "1": {"Channels": {"0": 10000, "2": 200, "3": 6, "4": 40, "5": 0, "45": 8}},
                    }
                },
                {
                    "Cars": {
                        "1": {"Channels": {"0": 11200, "2": 298, "3": 8, "4": 99, "5": 0, "45": 12}},
                    }
                },
            ]
        }
    )
    car = cardata()["1"]
    assert car["speed"] == 298
    assert car["throttle"] == 99
    assert car["rpm"] == 11200


def test_zandvoort_windows_sprint_then_replay():
    live_at = datetime(2026, 8, 22, 10, 15, tzinfo=timezone.utc)
    win = matching_window(live_at)
    assert win is not None
    assert win["session_type"] == "S"
    after = datetime(2026, 8, 22, 11, 20, tzinfo=timezone.utc)
    assert matching_window(after) is None
    ended = just_ended_window(after)
    assert ended is not None
    assert ended["session_type"] == "S"
    nxt = next_window(after)
    assert nxt is not None
    assert nxt["session_type"] == "Q"


def test_race_window_sunday():
    race = matching_window(datetime(2026, 8, 23, 13, 30, tzinfo=timezone.utc))
    assert race is not None
    assert race["session_type"] == "R"


def test_delay_note_flags_stale_feed():
    assert "1.2s stale" in delay_note(1.2, connected=True, source="SignalR")
    assert "STALE" in delay_note(25.0, connected=True, source="SignalR")
    assert "first timing" in delay_note(None, connected=True, source="SignalR")


def test_build_live_race_state_from_snapshot():
    from aris.live_feed import DriverLive

    snap = LiveSnapshot(
        mode="live",
        is_live=True,
        source="signalr",
        session_name="Sprint",
        session_type="S",
        year=2026,
        round_number=15,
        circuit="Zandvoort",
        country="Netherlands",
        current_lap=9,
        total_laps=24,
        flag="GREEN",
        remaining_s=1200,
        elapsed_s=600,
        feed_age_s=1.1,
        delay_note="ok",
        air_temp=18.0,
        track_temp=27.0,
        rainfall=False,
        drivers=[
            DriverLive(
                number=1,
                code="VER",
                name="Max VERSTAPPEN",
                team="Red Bull",
                position=2,
                gap_to_leader_s=1.2,
                gap_to_ahead_s=1.2,
                last_lap_ms=73000,
                best_lap_ms=72500,
                compound="M",
                tyre_life=9,
                n_laps=9,
            )
        ],
    )
    state = build_live_race_state(snap, "VER")
    assert state is not None
    assert state.driver_code == "VER"
    assert state.compound == "MEDIUM"
    assert state.tyre_life == 9
    assert state.total_laps == 24
    assert state.laps_remaining == 15
    assert state.session_id == 0
    assert state.lag1_pace == 73.0
