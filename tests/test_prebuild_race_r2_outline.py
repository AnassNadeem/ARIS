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
