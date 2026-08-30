"""Audit helpers for R2 race_field.json vs FastF1 facts. No live FastF1."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_race_accuracy.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_race_accuracy", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _field(**over):
    payload = {
        "meta": {"year": 2025, "round": 1, "circuit_name": "Melbourne"},
        "drivers": [
            {"code": "VER"},
            {"code": "NOR"},
            {"code": "PIA"},
            {"code": "HUL"},
        ],
        "laps": [
            {"lap": 1, "driver": "VER", "track_status": "1", "is_dnf": False},
            {"lap": 2, "driver": "VER", "track_status": "4", "is_dnf": False},
            {"lap": 3, "driver": "VER", "track_status": "4", "is_dnf": False},
            {"lap": 4, "driver": "VER", "track_status": "1", "is_dnf": False},
            {"lap": 1, "driver": "NOR", "track_status": "1", "is_dnf": False},
            {"lap": 2, "driver": "NOR", "track_status": "4", "is_dnf": False},
            {"lap": 3, "driver": "NOR", "track_status": "4", "is_dnf": True},
            {"lap": 1, "driver": "PIA", "track_status": "1", "is_dnf": False},
        ],
        "weather": [
            {"lap": 1, "rainfall": False},
            {"lap": 2, "rainfall": True},
            {"lap": 3, "rainfall": True},
            {"lap": 4, "rainfall": False},
        ],
        "race_control": [],
    }
    payload.update(over)
    return payload


def test_merge_runs_and_track_flag():
    mod = _load()
    assert [p.key() for p in mod.merge_runs([2, 3, 5, 6, 7, 10])] == [(2, 3), (5, 7), (10, 10)]
    assert mod._flag_from_track_status("124") == "SC"
    assert mod._flag_from_track_status("671") == "VSC"
    assert mod._flag_from_track_status("5") == "RED"
    assert mod._flag_from_track_status("1") == "GREEN"
    assert mod._status_kind("Lapped", 56, 15) == "finished"
    assert mod._status_kind("Retired", 32, "R") == "dnf"
    assert mod._status_kind("Did not start", 0, "W") == "dns"


def test_facts_from_field_dnf_dns_sc_wet():
    mod = _load()
    facts = mod.facts_from_field(_field())
    assert facts.dnf == [("NOR", 3)]
    assert facts.dns == ["HUL"]
    assert [p.key() for p in facts.sc] == [(2, 3)]
    assert facts.vsc == []
    assert facts.red == []
    assert facts.wet_ever is True
    assert facts.wet_laps == [2, 3]
    assert "race_control_empty" in facts.notes


def test_red_restart_standing_from_race_control():
    mod = _load()
    payload = _field(
        laps=[
            {"lap": 8, "driver": "VER", "track_status": "5", "is_dnf": False},
            {"lap": 9, "driver": "VER", "track_status": "5", "is_dnf": False},
            {"lap": 10, "driver": "VER", "track_status": "1", "is_dnf": False},
        ],
        race_control=[
            {"lap": 8, "message": "RED FLAG", "flag": "RED", "category": None},
            {"lap": 10, "message": "STANDING START", "flag": None, "category": None},
        ],
        drivers=[{"code": "VER"}],
        weather=[{"lap": 8, "rainfall": False}],
    )
    facts = mod.facts_from_field(payload)
    assert len(facts.red) == 1
    assert facts.red[0].key() == (8, 9)
    assert facts.red[0].extra == "standing"
    assert "race_control_empty" not in facts.notes


def test_compare_pass_and_mismatch():
    mod = _load()
    aris = mod.facts_from_field(_field())
    ff1 = mod.RaceFacts(
        year=2025,
        round=1,
        circuit="Melbourne",
        dnf=[("NOR", 3)],
        dns=["HUL"],
        sc=[mod.Period(2, 3)],
        vsc=[],
        red=[],
        wet_laps=[2, 3],
        wet_ever=True,
        race_control_n=12,
        notes=["ff1_race_control_n=12"],
    )
    ok = mod.compare_facts(aris, ff1)
    assert ok["ok"] is True
    ff1.dnf = [("NOR", 2)]
    ff1.dns = []
    bad = mod.compare_facts(aris, ff1)
    assert bad["ok"] is False
    assert bad["fields"]["dnf"]["status"] == "mismatch"
    assert bad["fields"]["dns"]["status"] == "mismatch"


def test_facts_from_session_classifies_results():
    mod = _load()
    results = pd.DataFrame(
        {
            "Abbreviation": ["VER", "NOR", "HUL"],
            "Status": ["Finished", "Accident", "Did not start"],
            "ClassifiedPosition": [1, "R", "W"],
        }
    )
    laps = pd.DataFrame(
        {
            "Driver": ["VER", "VER", "NOR"],
            "LapNumber": [1, 2, 1],
            "TrackStatus": ["1", "4", "1"],
            "LapStartTime": [
                pd.Timedelta(seconds=0),
                pd.Timedelta(seconds=90),
                pd.Timedelta(seconds=0),
            ],
        }
    )
    weather = pd.DataFrame(
        {
            "Time": [pd.Timedelta(seconds=0), pd.Timedelta(seconds=100)],
            "Rainfall": [False, True],
        }
    )
    rc = pd.DataFrame(
        {
            "Lap": [2],
            "Message": ["SAFETY CAR DEPLOYED"],
            "Flag": ["SC"],
            "Category": ["SafetyCar"],
        }
    )
    sess = SimpleNamespace(
        results=results,
        laps=laps,
        weather_data=weather,
        race_control_messages=rc,
        messages=None,
    )
    facts = mod.facts_from_session(sess, 2024, 3, "Suzuka")
    assert facts.dnf == [("NOR", 1)]
    assert facts.dns == ["HUL"]
    assert [p.key() for p in facts.sc] == [(2, 2)]
    assert facts.race_control_n == 1
    assert facts.wet_ever is True
