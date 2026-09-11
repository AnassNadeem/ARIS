"""R2 race_field outline is a single-lap circuit, not a full-race GPS dump."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prebuild_race_r2.py"


def _load():
    spec = importlib.util.spec_from_file_location("prebuild_race_r2", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_outline_uses_circuit_map_quick(monkeypatch):
    mod = _load()
    cmap = SimpleNamespace(available=True, x=[20.0, 120.0, 220.0, 20.0], y=[20.0, 80.0, 20.0, 20.0])
    monkeypatch.setattr("backend.sessions.circuit_map_quick", lambda *_a, **_k: cmap)
    # One point is not a usable GPS outline — circuit_map_quick still wins.
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: {"x": [999.0], "y": [999.0]})
    out = mod._outline(SimpleNamespace(), 2025, 15)
    assert out["x"] == cmap.x
    assert out["y"] == cmap.y


def test_outline_prefers_session_gps_over_prior_year_map(monkeypatch):
    mod = _load()
    cmap = SimpleNamespace(
        available=True, x=[20.0, 120.0, 220.0, 20.0], y=[20.0, 80.0, 20.0, 20.0]
    )
    gps = {"x": [1000.0, 2000.0, 1500.0, 1000.0], "y": [500.0, 800.0, 100.0, 500.0]}
    monkeypatch.setattr("backend.sessions.circuit_map_quick", lambda *_a, **_k: cmap)
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: gps)
    outline, source = mod._outline_with_source(SimpleNamespace(), 2026, 16)
    assert source == "gps_fallback"
    assert outline == gps


def test_outline_falls_back_when_circuit_map_quick_fails(monkeypatch):
    mod = _load()

    def boom(*_a, **_k):
        raise RuntimeError("no map")

    monkeypatch.setattr("backend.sessions.circuit_map_quick", boom)
    monkeypatch.setattr(
        mod,
        "_one_lap_gps",
        lambda *_a, **_k: {"x": [1.0, 2.0, 1.0], "y": [0.0, 1.0, 0.0]},
    )
    out = mod._outline(SimpleNamespace(), 2025, 15)
    assert out == {"x": [1.0, 2.0, 1.0], "y": [0.0, 1.0, 0.0]}


def test_outline_falls_back_when_circuit_map_quick_empty(monkeypatch):
    mod = _load()
    cmap = SimpleNamespace(available=False, x=[], y=[], error="missing")
    monkeypatch.setattr("backend.sessions.circuit_map_quick", lambda *_a, **_k: cmap)
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: {"x": [3.0, 4.0], "y": [5.0, 6.0]})
    out = mod._outline(SimpleNamespace(), 2024, 15)
    assert out["x"] == [3.0, 4.0]


def test_outline_with_source_marks_circuit_map_quick(monkeypatch):
    mod = _load()
    cmap = SimpleNamespace(available=True, x=[20.0, 120.0, 20.0], y=[20.0, 80.0, 20.0])
    monkeypatch.setattr("backend.sessions.circuit_map_quick", lambda *_a, **_k: cmap)
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: {"x": [999.0], "y": [999.0]})
    outline, source = mod._outline_with_source(SimpleNamespace(), 2025, 15)
    assert source == "circuit_map_quick"
    assert outline["x"] == cmap.x


def test_outline_with_source_marks_gps_fallback(monkeypatch):
    mod = _load()

    def boom(*_a, **_k):
        raise RuntimeError("no map")

    gps = {"x": [1.0, 2.0, 1.0], "y": [0.0, 1.0, 0.0]}
    monkeypatch.setattr("backend.sessions.circuit_map_quick", boom)
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: gps)
    outline, source = mod._outline_with_source(SimpleNamespace(), 2025, 15)
    assert source == "gps_fallback"
    assert outline == gps


def test_build_race_field_records_outline_source(monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        mod,
        "_outline_with_source",
        lambda *_a, **_k: ({"x": [20.0, 120.0], "y": [20.0, 80.0]}, "circuit_map_quick"),
    )
    monkeypatch.setattr(mod, "_drivers", lambda *_a, **_k: [])
    monkeypatch.setattr(mod, "_laps_stints", lambda *_a, **_k: ([], []))
    monkeypatch.setattr(mod, "_weather", lambda *_a, **_k: [])
    monkeypatch.setattr(mod, "_race_control", lambda *_a, **_k: [])
    monkeypatch.setattr(mod, "_pos_samples", lambda *_a, **_k: {})
    monkeypatch.setattr(mod, "_green_flag_s", lambda *_a, **_k: 0.0)
    monkeypatch.setattr(mod, "_session_key", lambda *_a, **_k: 1)
    monkeypatch.setattr(mod, "_outline_is_map_space", lambda *_a, **_k: False)
    rnd = SimpleNamespace(
        circuit_name="Zandvoort", name="Netherlands", date_race=None, total_laps=72
    )
    monkeypatch.setattr("backend.calendar.get_round", lambda *_a, **_k: rnd)
    field = mod.build_race_field(2025, 15, SimpleNamespace())
    assert field["meta"]["outline_source"] == "circuit_map_quick"
    assert field["outline"]["x"] == [20.0, 120.0]


def test_lap_fracs_shift_when_position_clock_does_not_overlap_laps():
    mod = _load()
    # Position Date in unix seconds, lap starts as session-relative seconds.
    times = [1_700_000_000.0 + i for i in range(0, 200, 10)]
    starts = [(0.0, 1, 90.0), (90.0, 2, 90.0)]
    fracs = mod._lap_fracs_for_times(times, starts)
    assert max(fracs) > 1.0
    assert fracs[0] < 0.2
    assert fracs[-1] > 1.0


def test_fill_start_durations_uses_gap_when_lap_time_missing():
    mod = _load()
    filled = mod._fill_start_durations(
        [(0.0, 1, 88.0), (88.0, 2, None), (200.0, 3, 90.0)]
    )
    assert filled[0][2] == 88.0
    assert filled[1][2] == 112.0
    assert filled[2][2] == 90.0


def test_collapse_duplicate_lap_fracs_keeps_last_of_run():
    mod = _load()
    rows = (
        [{"lap_frac": 0.0, "path_frac": i / 10, "speed_kph": 0} for i in range(8)]
        + [{"lap_frac": 0.2, "path_frac": 0.3, "speed_kph": 200}]
        + [{"lap_frac": 2.999, "path_frac": 0.01, "speed_kph": 0} for _ in range(5)]
    )
    out = mod._collapse_duplicate_lap_fracs(rows)
    assert [r["lap_frac"] for r in out] == [0.0, 0.2, 2.999]
    assert out[0]["path_frac"] == 0.7
    assert out[2]["path_frac"] == 0.01


def test_classified_is_integer_rejects_non_numeric():
    mod = _load()
    assert mod._classified_is_integer(18) is True
    assert mod._classified_is_integer("7") is True
    assert mod._classified_is_integer(18.0) is True
    assert mod._classified_is_integer(None) is False
    assert mod._classified_is_integer(float("nan")) is False
    assert mod._classified_is_integer("R") is False
    assert mod._classified_is_integer("D") is False
    assert mod._classified_is_integer("E") is False
    assert mod._classified_is_integer("N") is False
    assert mod._classified_is_integer("W") is False
    assert mod._classified_is_integer("NC") is False


def test_mark_dnf_skips_classified_finisher_with_retired_status():
    mod = _load()
    results = pd.DataFrame(
        {
            "Abbreviation": ["RUS", "MAG", "VER", "ALO"],
            "Status": ["Retired", "Retired", "Finished", "Accident"],
            "ClassifiedPosition": [18, "R", 1, "R"],
        }
    )
    laps = [
        {"driver": "RUS", "lap": 56, "is_dnf": False},
        {"driver": "RUS", "lap": 57, "is_dnf": False},
        {"driver": "MAG", "lap": 10, "is_dnf": False},
        {"driver": "VER", "lap": 57, "is_dnf": False},
        {"driver": "ALO", "lap": 22, "is_dnf": False},
    ]
    mod._mark_dnf(laps, SimpleNamespace(results=results))
    by = {(r["driver"], r["lap"]): r["is_dnf"] for r in laps}
    assert by[("RUS", 56)] is False
    assert by[("RUS", 57)] is False
    assert by[("MAG", 10)] is True
    assert by[("VER", 57)] is False
    assert by[("ALO", 22)] is True


def test_mark_dnf_skips_dns_and_driver_is_dns():
    mod = _load()
    rec = SimpleNamespace(Status="Did not start", ClassifiedPosition="W")
    assert mod._driver_is_dns(rec) is True
    results = pd.DataFrame(
        {
            "Abbreviation": ["HUL", "MAG"],
            "Status": ["Did not start", "Accident"],
            "ClassifiedPosition": ["W", "R"],
        }
    )
    laps = [
        {"driver": "HUL", "lap": 1, "is_dnf": False},
        {"driver": "MAG", "lap": 4, "is_dnf": False},
    ]
    mod._mark_dnf(laps, SimpleNamespace(results=results))
    by = {r["driver"]: r["is_dnf"] for r in laps}
    assert by["HUL"] is False
    assert by["MAG"] is True


def test_weather_joins_on_lap_start_not_row_index():
    mod = _load()
    # Two weather samples, five laps. Index interpolation would paint later
    # laps wet from the far-future rain row; nearest-in-time keeps them dry.
    weather = pd.DataFrame(
        {
            "Time": [pd.Timedelta(seconds=0), pd.Timedelta(seconds=10_000)],
            "Rainfall": [False, True],
            "TrackTemp": [40.0, 20.0],
            "AirTemp": [25.0, 15.0],
        }
    )
    ff1_laps = pd.DataFrame(
        {
            "Driver": ["VER"] * 5,
            "LapNumber": [1, 2, 3, 4, 5],
            "LapStartTime": [pd.Timedelta(seconds=90 * i) for i in range(5)],
        }
    )
    built = [{"lap": i, "driver": "VER"} for i in range(1, 6)]
    out = mod._weather(SimpleNamespace(weather_data=weather, laps=ff1_laps), built)
    assert [r["rainfall"] for r in out] == [False, False, False, False, False]
    assert out[0]["track_temp_c"] == 40.0


def test_weather_uses_nearest_sample_preferring_not_after_on_tie():
    mod = _load()
    weather = pd.DataFrame(
        {
            "Time": [
                pd.Timedelta(seconds=0),
                pd.Timedelta(seconds=200),
                pd.Timedelta(seconds=400),
            ],
            "Rainfall": [False, True, False],
            "TrackTemp": [45.0, 30.0, 28.0],
            "AirTemp": [22.0, 18.0, 17.0],
        }
    )
    ff1_laps = pd.DataFrame(
        {
            "Driver": ["NOR"] * 5,
            "LapNumber": [1, 2, 3, 4, 5],
            "LapStartTime": [
                pd.Timedelta(seconds=0),
                pd.Timedelta(seconds=90),
                pd.Timedelta(seconds=199),
                pd.Timedelta(seconds=270),
                pd.Timedelta(seconds=450),
            ],
        }
    )
    built = [{"lap": i, "driver": "NOR"} for i in range(1, 6)]
    out = mod._weather(SimpleNamespace(weather_data=weather, laps=ff1_laps), built)
    # t=199 is 1s from rain@200 and 199s from dry@0 → nearest is rain.
    # t=270 is nearer rain@200 than dry@400. t=450 is nearest dry@400.
    assert [r["rainfall"] for r in out] == [False, False, True, True, False]
    assert math.isclose(out[3]["track_temp_c"], 30.0)


def test_chequered_flag_is_not_red_track_status():
    mod = _load()
    code = mod._track_status_code_from_rc
    assert code({"flag": "CHEQUERED", "message": "CHEQUERED FLAG"}) == "1"
    assert code({"flag": None, "message": "CHEQUERED FLAG"}) == "1"
    assert code({"flag": "RED", "message": "RED FLAG - RACE SUSPENDED"}) == "5"
    assert code({"flag": None, "message": "RED FLAG"}) == "5"
    assert code({"flag": None, "message": "SAFETY CAR LIGHTS ON"}) is None
    assert code({"flag": None, "message": "SAFETY CAR DEPLOYED"}) == "4"
    assert code({"flag": None, "message": "VSC DEPLOYED"}) == "6"
    assert code({"flag": None, "message": "VSC ENDING"}) == "1"
    assert code({"flag": None, "message": "STANDING START"}) == "1"


def test_apply_rc_track_status_follows_monza_2026_sequence():
    mod = _load()
    laps = [{"lap": n, "driver": "VER", "track_status": "1245"} for n in range(1, 54)]
    rc = [
        {"lap": 3, "flag": "YELLOW", "message": "YELLOW IN TRACK SECTOR 15"},
        {"lap": 3, "flag": None, "message": "SAFETY CAR DEPLOYED"},
        {"lap": 3, "flag": None, "message": "RED FLAG - RACE SUSPENDED"},
        {"lap": 4, "flag": None, "message": "STANDING START"},
        {"lap": 5, "flag": None, "message": "STANDING START"},
        {"lap": 28, "flag": None, "message": "VSC DEPLOYED"},
        {"lap": 29, "flag": None, "message": "VSC ENDING"},
        {"lap": 53, "flag": "CHEQUERED", "message": "CHEQUERED FLAG"},
    ]
    mod._apply_race_control_track_status(laps, rc)
    by = {int(r["lap"]): r["track_status"] for r in laps}
    assert by[1] == "1"
    assert by[2] == "1"
    assert by[3] == "5"
    assert by[4] == "1"
    assert by[5] == "1"
    assert by[6] == "1"
    assert by[13] == "1"
    assert by[27] == "1"
    assert by[28] == "6"
    assert by[29] == "1"
    assert by[52] == "1"
    assert by[53] == "1"


def test_race_control_rows_keep_fastf1_date(monkeypatch):
    mod = _load()
    monkeypatch.setattr(
        "backend.sessions._ff1_race_control_rows",
        lambda *_a, **_k: [
            {
                "lap_number": 53,
                "message": "CHEQUERED FLAG",
                "flag": "CHEQUERED",
                "category": "Flag",
                "date": "2026-09-06T14:54:46+00:00",
            }
        ],
    )
    rows = mod._race_control(SimpleNamespace())
    assert rows == [
        {
            "lap": 53,
            "message": "CHEQUERED FLAG",
            "flag": "CHEQUERED",
            "category": "Flag",
            "date": "2026-09-06T14:54:46+00:00",
        }
    ]
