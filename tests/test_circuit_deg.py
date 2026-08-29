"""T2-A circuit-conditioned deg slopes (flagged)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aris.physics.tires import (
    CIRCUIT_DEG_ENV,
    DEFAULT_COMPOUND_SLOPE,
    circuit_deg_enabled,
    clear_circuit_deg_cache,
    get_compound_slopes,
)
from aris.recommend import recommend
from aris.simulate import ActionKind
from aris.state import RaceState
from aris.tracks import clear_track_config_cache, load_track_config


@pytest.fixture(autouse=True)
def _reset_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(CIRCUIT_DEG_ENV, raising=False)
    clear_circuit_deg_cache()
    clear_track_config_cache()
    yield
    clear_circuit_deg_cache()
    clear_track_config_cache()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_zero_env_is_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "0")
    assert circuit_deg_enabled() is False
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "false")
    assert circuit_deg_enabled() is False
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "1")
    assert circuit_deg_enabled() is True


def test_flag_off_returns_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"train_years": [2018, 2023], "max_year": 2023},
        "bahrain": {"SOFT": {"slope": 0.2, "n_stints": 9, "std": 0.01}},
    }
    path = tmp_path / "circuit_deg_slopes.json"
    _write_json(path, payload)
    monkeypatch.setattr("aris.physics.tires.CIRCUIT_DEG_PATH", path)
    assert get_compound_slopes("bahrain", 2024) == dict(DEFAULT_COMPOUND_SLOPE)


def test_missing_pair_keeps_prior(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"train_years": [2023], "max_year": 2023},
        "bahrain": {"MEDIUM": {"slope": 0.044, "n_stints": 22, "std": 0.01}},
    }
    path = tmp_path / "circuit_deg_slopes.json"
    _write_json(path, payload)
    monkeypatch.setattr("aris.physics.tires.CIRCUIT_DEG_PATH", path)
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "1")
    clear_circuit_deg_cache()
    slopes = get_compound_slopes("bahrain", 2024)
    assert slopes["MEDIUM"] == pytest.approx(0.044)
    assert slopes["SOFT"] == pytest.approx(DEFAULT_COMPOUND_SLOPE["SOFT"])
    assert slopes["HARD"] == pytest.approx(DEFAULT_COMPOUND_SLOPE["HARD"])


def test_n_stints_below_three_omits_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"train_years": [2023], "max_year": 2023},
        "bahrain": {"SOFT": {"slope": 0.2, "n_stints": 2, "std": 0.01}},
    }
    path = tmp_path / "circuit_deg_slopes.json"
    _write_json(path, payload)
    monkeypatch.setattr("aris.physics.tires.CIRCUIT_DEG_PATH", path)
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "1")
    clear_circuit_deg_cache()
    slopes = get_compound_slopes("bahrain", 2024)
    assert slopes["SOFT"] == pytest.approx(DEFAULT_COMPOUND_SLOPE["SOFT"])


def test_max_year_blocks_leakage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"train_years": [2018, 2023], "max_year": 2023},
        "bahrain": {"SOFT": {"slope": 0.2, "n_stints": 9, "std": 0.01}},
    }
    path = tmp_path / "circuit_deg_slopes.json"
    _write_json(path, payload)
    monkeypatch.setattr("aris.physics.tires.CIRCUIT_DEG_PATH", path)
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "1")
    clear_circuit_deg_cache()
    slopes = get_compound_slopes("bahrain", 2023)
    assert slopes == dict(DEFAULT_COMPOUND_SLOPE)


def test_zandvoort_alias_and_load_track_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"train_years": [2021, 2022, 2023], "max_year": 2023},
        "netherlands": {
            "MEDIUM": {"slope": 0.044, "n_stints": 22, "std": 0.012},
            "HARD": {"slope": 0.027, "n_stints": 18, "std": 0.009},
        },
    }
    path = tmp_path / "circuit_deg_slopes.json"
    _write_json(path, payload)
    monkeypatch.setattr("aris.physics.tires.CIRCUIT_DEG_PATH", path)
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "1")
    clear_circuit_deg_cache()
    slopes = get_compound_slopes("zandvoort", 2025)
    assert slopes["MEDIUM"] == pytest.approx(0.044)
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    assert cfg.compound_slopes is not None
    assert cfg.compound_slopes["HARD"] == pytest.approx(0.027)


def test_true_compound_overlay_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"train_years": [2023], "max_year": 2023},
        "netherlands": {"MEDIUM": {"slope": 0.99, "n_stints": 22, "std": 0.01}},
    }
    path = tmp_path / "circuit_deg_slopes.json"
    _write_json(path, payload)
    monkeypatch.setattr("aris.physics.tires.CIRCUIT_DEG_PATH", path)
    monkeypatch.setenv(CIRCUIT_DEG_ENV, "1")
    monkeypatch.setenv("ARIS_TRUE_COMPOUND_SLOPES", "pooled")
    clear_circuit_deg_cache()
    clear_track_config_cache()
    cfg = load_track_config("Netherlands", year=2025, round_no=15)
    assert cfg.compound_slopes is None or cfg.compound_slopes.get("MEDIUM") != pytest.approx(0.99)


def _zandvoort_state() -> RaceState:
    from aris.models.features import estimate_fuel_kg

    return RaceState(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2025,
        round_no=15,
        country="Netherlands",
        lap_number=25,
        compound="MEDIUM",
        tyre_life=2,
        fuel_kg=estimate_fuel_kg(25, total_laps=72),
        laps_remaining=47,
        total_laps=72,
        lag1_pace=74.0,
        lag2_pace=74.0,
        stint_roll3=74.0,
        pit_compound="HARD",
    )


def test_zandvoort_identity_flag_off():
    from aris.recommend import pit_window_compound_times

    state = _zandvoort_state()
    for pit_lap in (33, 30):
        times = pit_window_compound_times(state, pit_lap)
        print(
            f"Pit lap {pit_lap}: HARD = {times['HARD']:.1f} s, "
            f"MEDIUM = {times['MEDIUM']:.1f} s, SOFT = {times['SOFT']:.1f} s."
        )
        assert times["HARD"] <= times["MEDIUM"], (
            f"MEDIUM beat HARD at pit lap {pit_lap}: {times}"
        )
        assert times["HARD"] <= times["SOFT"], (
            f"SOFT beat HARD at pit lap {pit_lap}: {times}"
        )
    result = recommend(state, top_k=3, mc_draws=0)
    labels = [r.label for r in result.recommendations]
    assert labels[0].startswith("Pit lap 33 for HARD")
    assert any(l.startswith("Pit lap 30 for HARD") for l in labels)
    assert any(r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps for r in result.recommendations)


def test_zandvoort_identity_with_dirty_air_history_flag_off():
    """Dirty air is undercut-only; default ranking must ignore close-following gaps."""
    state = _zandvoort_state().model_copy(
        update={"gap_ahead_history": [0.8, 0.7, 0.9], "gap_ahead_s": 0.8}
    )
    result = recommend(state, top_k=3, mc_draws=0)
    assert result.recommendations[0].label.startswith("Pit lap 33 for HARD")
