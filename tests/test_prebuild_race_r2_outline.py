"""R2 race_field outline is a single-lap circuit, not a full-race GPS dump."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

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
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: {"x": [999.0], "y": [999.0]})
    out = mod._outline(SimpleNamespace(), 2025, 15)
    assert out["x"] == cmap.x
    assert out["y"] == cmap.y


def test_outline_falls_back_when_circuit_map_quick_fails(monkeypatch):
    mod = _load()

    def boom(*_a, **_k):
        raise RuntimeError("no map")

    monkeypatch.setattr("backend.sessions.circuit_map_quick", boom)
    monkeypatch.setattr(mod, "_one_lap_gps", lambda *_a, **_k: {"x": [1.0, 2.0, 1.0], "y": [0.0, 1.0, 0.0]})
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
