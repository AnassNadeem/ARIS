"""--all-drivers bakes every race_field.json driver without reloading FastF1."""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prebuild_race_r2.py"


def _load():
    spec = importlib.util.spec_from_file_location("prebuild_race_r2_all_drivers", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _field(codes: list[str], *, dns: list[str] | None = None) -> dict:
    skip = {c.upper() for c in (dns or [])}
    drivers = []
    laps = []
    for i, raw in enumerate(codes):
        code = raw.upper()
        drivers.append(
            {
                "code": code,
                "name": code,
                "team": "Test",
                "colour": "#111111",
                "grid_position": i + 1,
                "is_dns": code in skip,
            }
        )
        if code in skip:
            continue
        laps.append(
            {
                "lap": 1,
                "driver": code,
                "position": i + 1,
                "lap_time_s": 90.0 + i,
                "compound": "MEDIUM",
                "tyre_life": 1,
                "pit_this_lap": False,
            }
        )
    return {
        "meta": {"year": 2026, "round": 6, "total_laps": 1, "circuit_name": "Miami"},
        "drivers": drivers,
        "laps": laps,
    }


def _write_field(root: Path, year: int, rnd: int, field: dict) -> Path:
    path = root / "replay" / str(year) / str(rnd) / "race_field.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(field), encoding="utf-8")
    return path


def test_driver_codes_from_field_reads_drivers_array_in_order():
    mod = _load()
    field = _field(["ANT", "VER", "LEC"])
    field["drivers"].append({"code": "VER", "name": "dup"})
    field["drivers"].append({"name": "no-code"})
    assert mod.driver_codes_from_field(field) == ["ANT", "VER", "LEC"]


def test_all_drivers_uses_local_field_without_fastf1(tmp_path, monkeypatch, caplog):
    mod = _load()
    monkeypatch.setattr(mod, "LOCAL_ROOT", tmp_path)
    _write_field(tmp_path, 2026, 6, _field(["ANT", "VER", "LEC"]))

    def boom(*_a, **_k):
        raise AssertionError("must not load FastF1 when race_field.json is local")

    monkeypatch.setattr(mod, "_load_session", boom)
    monkeypatch.setattr(mod, "_fetch_remote_field", lambda *_a, **_k: None)
    built: list[str] = []

    def fake_ghost(year, rnd, driver, sess, field):
        built.append(driver)
        assert sess is None
        assert [r["code"] for r in field["drivers"]] == ["ANT", "VER", "LEC"]
        return {"driver": driver, "ticks": [{"lap": 1}]}

    monkeypatch.setattr(mod, "build_ghost", fake_ghost)
    caplog.set_level(logging.INFO)
    out = mod.build_all_drivers(
        2026, 6, "Miami", skip_existing=False, no_upload=True
    )
    assert out["field_source"] == "local"
    assert built == ["ANT", "VER", "LEC"]
    assert out["succeeded"] == ["ANT", "VER", "LEC"]
    assert out["failed"] == []
    assert (tmp_path / "replay" / "2026" / "6" / "ghost_ANT.json").is_file()
    assert "Building 2026 R6 Miami: ANT (1/3)..." in caplog.text
    assert "Building 2026 R6 Miami: VER (2/3)..." in caplog.text
    assert "FastF1 not loaded" in caplog.text


def test_all_drivers_continues_after_one_driver_fails(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "LOCAL_ROOT", tmp_path)
    _write_field(tmp_path, 2026, 6, _field(["ANT", "VER", "LEC"]))
    monkeypatch.setattr(mod, "_load_session", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("no FastF1")
    ))

    def fake_ghost(_year, _rnd, driver, _sess, _field):
        if driver == "VER":
            raise RuntimeError("ghost boom")
        return {"driver": driver, "ticks": []}

    monkeypatch.setattr(mod, "build_ghost", fake_ghost)
    out = mod.build_all_drivers(
        2026, 6, "Miami", skip_existing=False, no_upload=True
    )
    assert out["succeeded"] == ["ANT", "LEC"]
    assert [row["driver"] for row in out["failed"]] == ["VER"]
    assert "ghost boom" in out["failed"][0]["error"]
    assert (tmp_path / "replay" / "2026" / "6" / "ghost_ANT.json").is_file()
    assert not (tmp_path / "replay" / "2026" / "6" / "ghost_VER.json").exists()
    assert (tmp_path / "replay" / "2026" / "6" / "ghost_LEC.json").is_file()


def test_all_drivers_skip_existing_skips_one_ghost(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "LOCAL_ROOT", tmp_path)
    _write_field(tmp_path, 2026, 6, _field(["ANT", "VER"]))
    monkeypatch.setattr(
        mod,
        "_r2_exists",
        lambda year, rnd, name: name == "ghost_ANT.json",
    )
    built: list[str] = []
    monkeypatch.setattr(
        mod,
        "build_ghost",
        lambda _y, _r, driver, _s, _f: built.append(driver) or {"driver": driver},
    )
    out = mod.build_all_drivers(
        2026, 6, "Miami", skip_existing=True, no_upload=True
    )
    assert out["skipped"] == ["ANT"]
    assert out["succeeded"] == ["VER"]
    assert built == ["VER"]


def test_all_drivers_loads_session_once_when_field_missing(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "LOCAL_ROOT", tmp_path)
    calls = {"n": 0}

    def fake_session(*_a, **_k):
        calls["n"] += 1
        return SimpleNamespace()

    field = _field(["NOR", "PIA"])
    monkeypatch.setattr(mod, "_load_session", fake_session)
    monkeypatch.setattr(mod, "_fetch_remote_field", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "build_race_field", lambda *_a, **_k: field)
    monkeypatch.setattr(mod, "_fit_pos_under_budget", lambda payload, _n: b"{}")
    monkeypatch.setattr(
        mod,
        "build_ghost",
        lambda *_a, **_k: {"driver": "x", "ticks": []},
    )
    out = mod.build_all_drivers(
        2026, 6, "Miami", skip_existing=False, no_upload=True
    )
    assert calls["n"] == 1
    assert out["field_source"] == "fastf1"
    assert out["succeeded"] == ["NOR", "PIA"]
    assert (tmp_path / "replay" / "2026" / "6" / "race_field.json").is_file()


def test_main_all_drivers_dispatches_without_build_one(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "LOCAL_ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "completed_jobs",
        lambda **_k: [(2026, 6, "Miami")],
    )
    seen: dict[str, object] = {}

    def fake_all(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return {
            "failed": [],
            "succeeded": ["VER"],
            "skipped": [],
            "field_source": "local",
        }

    monkeypatch.setattr(mod, "build_all_drivers", fake_all)

    def boom(*_a, **_k):
        raise AssertionError("single-driver build_one must not run")

    monkeypatch.setattr(mod, "build_one", boom)
    code = mod.main(["--year", "2026", "--round", "6", "--all-drivers", "--no-upload"])
    assert code == 0
    assert seen["args"][:3] == (2026, 6, "Miami")
    assert seen["kwargs"]["no_upload"] is True
    assert seen["kwargs"]["skip_existing"] is False
