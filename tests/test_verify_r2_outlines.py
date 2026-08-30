"""Closed-loop and outline-source checks for locally built R2 race fields."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_r2_outlines.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_r2_outlines", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _field(*, xs, ys, source=None, year=2024, round_number=1):
    meta = {"year": year, "round": round_number}
    if source is not None:
        meta["outline_source"] = source
    return {"meta": meta, "outline": {"x": xs, "y": ys}}


def test_closed_loop_pass_and_open_loop_fail():
    mod = _load()
    closed = mod.evaluate_field(
        _field(xs=[0.0, 100.0, 100.0, 0.0], ys=[0.0, 0.0, 80.0, 0.0], source="circuit_map_quick")
    )
    assert closed["ok"] is True
    assert closed["closed_loop"] == 0.0
    assert closed["source"] == "circuit_map_quick"

    opened = mod.evaluate_field(
        _field(xs=[0.0, 100.0], ys=[0.0, 0.0], source="circuit_map_quick")
    )
    assert opened["ok"] is False
    assert "open_loop" in opened["reasons"]
    assert opened["ratio"] is not None
    assert opened["ratio"] > 0.10


def test_gps_fallback_is_flagged_even_when_closed():
    mod = _load()
    row = mod.evaluate_field(
        _field(xs=[0.0, 10.0, 0.0], ys=[0.0, 10.0, 0.0], source="gps_fallback")
    )
    assert row["ok"] is False
    assert "gps_fallback" in row["reasons"]


def test_missing_marker_inferred_from_map_space():
    mod = _load()
    map_space = mod.evaluate_field(_field(xs=[20.0, 120.0, 20.0], ys=[20.0, 80.0, 20.0]))
    assert map_space["source"] == "circuit_map_quick"
    assert map_space["inferred"] is True
    assert map_space["ok"] is True

    gps = mod.evaluate_field(_field(xs=[0.0, 2000.0, 0.0], ys=[0.0, 500.0, 0.0]))
    assert gps["source"] == "gps_fallback"
    assert gps["inferred"] is True
    assert gps["ok"] is False


def test_evaluate_all_walks_replay_tree(tmp_path):
    mod = _load()
    race = tmp_path / "2025" / "15"
    race.mkdir(parents=True)
    payload = _field(
        xs=[20.0, 220.0, 20.0],
        ys=[20.0, 80.0, 20.0],
        source="circuit_map_quick",
        year=2025,
        round_number=15,
    )
    (race / "race_field.json").write_text(json.dumps(payload), encoding="utf-8")
    (race / "ghost_VER.json").write_text("{}", encoding="utf-8")
    rows = mod.evaluate_all(tmp_path)
    assert len(rows) == 1
    assert rows[0]["year"] == 2025
    assert rows[0]["round"] == 15
    assert rows[0]["ok"] is True
    assert "PASS" in mod.format_row(rows[0])
