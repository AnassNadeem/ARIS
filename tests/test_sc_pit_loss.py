"""T2-B — SC/VSC current-lap pit-loss multiplier (default napkin + flagged measure)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from aris.eval.sc_pit_loss import (
    MEASURED_SC_PIT_LOSS_ENV,
    MEASURED_SC_PIT_LOSS_PATH_ENV,
    clear_measured_sc_pit_loss_cache,
    heilmeier_implied_ratios,
    measure_sc_vsc_pit_events,
    measured_multiplier,
    summarize_events,
)
from aris.physics.tires import CIRCUIT_DEG_ENV, clear_circuit_deg_cache
from aris.recommend import recommend
from aris.simulate import (
    ActionKind,
    StrategyAction,
    get_pit_loss,
    simulate,
    simulate_full_race,
)
from aris.state import SC_PIT_LOSS_MULT, VSC_PIT_LOSS_MULT, sc_vsc_pit_multiplier
from aris.tracks import load_track_config
from tests.test_circuit_deg import _zandvoort_state
from tests.test_strategy import _sample_state


@pytest.fixture(autouse=True)
def _reset_measured_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(MEASURED_SC_PIT_LOSS_ENV, raising=False)
    monkeypatch.delenv(MEASURED_SC_PIT_LOSS_PATH_ENV, raising=False)
    monkeypatch.delenv(CIRCUIT_DEG_ENV, raising=False)
    clear_measured_sc_pit_loss_cache()
    clear_circuit_deg_cache()
    yield
    clear_measured_sc_pit_loss_cache()
    clear_circuit_deg_cache()


def test_get_pit_loss_green_is_full():
    assert get_pit_loss(18.5, "1") == 18.5
    assert get_pit_loss(18.5, None) == 18.5


def test_get_pit_loss_sc_is_35_percent():
    assert SC_PIT_LOSS_MULT == 0.35
    assert get_pit_loss(18.5, "4") == 18.5 * 0.35
    assert get_pit_loss(18.5, "24") == 18.5 * 0.35  # yellow + SC


def test_get_pit_loss_vsc_is_55_percent():
    assert VSC_PIT_LOSS_MULT == 0.55
    assert get_pit_loss(18.5, "6") == 18.5 * 0.55
    assert get_pit_loss(18.5, "7") == 18.5 * 0.55  # VSC ending


def test_sc_preferred_over_vsc_in_multicode():
    assert sc_vsc_pit_multiplier("46") == 0.35


def test_current_lap_pit_uses_reduced_loss():
    green = _sample_state(track_status="1", lap_number=20, laps_remaining=37)
    sc = _sample_state(track_status="4", lap_number=20, laps_remaining=37)
    action = StrategyAction(kind=ActionKind.PIT_NOW, pit_compound="HARD")
    green_out = simulate(green, action)
    sc_out = simulate(sc, action)
    assert sc_out.total_race_time_s < green_out.total_race_time_s
    pit = load_track_config("Bahrain", year=2024, round_no=1).pit_loss_s
    delta = green_out.total_race_time_s - sc_out.total_race_time_s
    assert abs(delta - (pit - get_pit_loss(pit, "4"))) < 1e-9


def test_future_pit_lap_keeps_full_loss_under_sc():
    green = _sample_state(track_status="1", lap_number=20, laps_remaining=37)
    sc = _sample_state(track_status="4", lap_number=20, laps_remaining=37)
    action = StrategyAction(kind=ActionKind.PIT_LAP, pit_lap=25, pit_compound="HARD")
    green_out = simulate(green, action)
    sc_out = simulate(sc, action)
    assert abs(green_out.total_race_time_s - sc_out.total_race_time_s) < 1e-9


def test_stay_out_delta_zero_under_sc():
    sc = _sample_state(track_status="4", lap_number=20, laps_remaining=37)
    out = simulate(sc, StrategyAction(kind=ActionKind.STAY_OUT))
    assert out.delta_vs_stay_out_s == 0.0


def test_pit_status_by_lap_is_opt_in_analysis():
    state = _sample_state(
        track_status="1", lap_number=1, laps_remaining=19, total_laps=20
    )
    green = simulate_full_race(state, pit_laps=[10], pit_compounds=["HARD"])
    discounted = simulate_full_race(
        state,
        pit_laps=[10],
        pit_compounds=["HARD"],
        pit_status_by_lap={10: "4"},
    )
    assert discounted < green


def _write_table(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_flag_off_ignores_measured_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"min_circuit_n": 5},
        "global": {"sc": 0.99, "vsc": 0.99},
        "by_circuit": {},
    }
    path = tmp_path / "sc.json"
    _write_table(path, payload)
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_PATH_ENV, str(path))
    clear_measured_sc_pit_loss_cache()
    assert measured_multiplier("sc") is None
    assert get_pit_loss(18.5, "4") == 18.5 * 0.35


def test_flag_on_uses_global_median(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    payload = {
        "meta": {"min_circuit_n": 5},
        "global": {"sc": 0.41, "vsc": 0.53, "n_sc": 20, "n_vsc": 12},
        "by_circuit": {},
    }
    path = tmp_path / "sc.json"
    _write_table(path, payload)
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_PATH_ENV, str(path))
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "1")
    clear_measured_sc_pit_loss_cache()
    assert get_pit_loss(18.5, "4") == pytest.approx(18.5 * 0.41)
    assert get_pit_loss(18.5, "6") == pytest.approx(18.5 * 0.53)


def test_flag_on_circuit_n_below_five_uses_global(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    payload = {
        "meta": {"min_circuit_n": 5},
        "global": {"sc": 0.41, "vsc": 0.53},
        "by_circuit": {
            "spain": {"sc": 0.10, "vsc": 0.10, "n_sc": 2, "n_vsc": 1},
        },
    }
    path = tmp_path / "sc.json"
    _write_table(path, payload)
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_PATH_ENV, str(path))
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "1")
    clear_measured_sc_pit_loss_cache()
    assert measured_multiplier("sc", "spain") == pytest.approx(0.41)


def test_flag_on_circuit_n_at_least_five_uses_circuit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    payload = {
        "meta": {"min_circuit_n": 5},
        "global": {"sc": 0.99, "vsc": 0.99},
        "by_circuit": {
            "spain": {"sc": 0.41, "vsc": 0.53, "n_sc": 5, "n_vsc": 6},
        },
    }
    path = tmp_path / "sc.json"
    _write_table(path, payload)
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_PATH_ENV, str(path))
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "1")
    clear_measured_sc_pit_loss_cache()
    assert get_pit_loss(18.5, "4", circuit_key="Spain") == pytest.approx(18.5 * 0.41)


def test_flag_on_missing_file_falls_back_to_napkin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_PATH_ENV, str(tmp_path / "missing.json"))
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "1")
    clear_measured_sc_pit_loss_cache()
    assert get_pit_loss(18.5, "4") == 18.5 * 0.35


def test_zero_env_is_off(monkeypatch: pytest.MonkeyPatch):
    from aris.eval.sc_pit_loss import measured_sc_pit_loss_enabled

    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "0")
    assert measured_sc_pit_loss_enabled() is False
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "false")
    assert measured_sc_pit_loss_enabled() is False
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "1")
    assert measured_sc_pit_loss_enabled() is True


def test_zandvoort_identity_with_measured_flag_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    payload = {
        "meta": {"min_circuit_n": 5},
        "global": {"sc": 0.10, "vsc": 0.10},
        "by_circuit": {
            "netherlands": {"sc": 0.10, "vsc": 0.10, "n_sc": 20, "n_vsc": 20},
        },
    }
    path = tmp_path / "sc.json"
    _write_table(path, payload)
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_PATH_ENV, str(path))
    monkeypatch.setenv(MEASURED_SC_PIT_LOSS_ENV, "1")
    clear_measured_sc_pit_loss_cache()
    result = recommend(_zandvoort_state(), top_k=3, mc_draws=0)
    labels = [r.label for r in result.recommendations]
    assert labels[0].startswith("Pit lap 33 for HARD")
    assert any(lab.startswith("Pit lap 30 for HARD") for lab in labels)
    assert any(
        r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps
        for r in result.recommendations
    )


def test_measure_net_vs_stayers_not_green_flying():
    field = pd.DataFrame(
        [
            {"driver_id": 1, "code": "A", "lap_number": 10, "lap_time_s": 127.0,
             "pit_in": True, "pit_out": False, "track_status": "4", "compound": "MEDIUM"},
            {"driver_id": 2, "code": "B", "lap_number": 10, "lap_time_s": 120.0,
             "pit_in": False, "pit_out": False, "track_status": "4", "compound": "MEDIUM"},
            {"driver_id": 3, "code": "C", "lap_number": 10, "lap_time_s": 121.0,
             "pit_in": False, "pit_out": False, "track_status": "4", "compound": "HARD"},
            {"driver_id": 4, "code": "D", "lap_number": 10, "lap_time_s": 119.0,
             "pit_in": False, "pit_out": False, "track_status": "4", "compound": "SOFT"},
        ]
    )
    events = measure_sc_vsc_pit_events(
        field, green_pit_loss_s=18.5, circuit_key="bahrain", year=2024, gp="Bahrain"
    )
    assert len(events) == 1
    assert events[0]["kind"] == "sc"
    assert events[0]["observed_net_s"] == pytest.approx(7.0)
    assert events[0]["ratio"] == pytest.approx(7.0 / 18.5, abs=1e-4)


def test_summarize_does_not_average_heilmeier():
    events = [
        {"kind": "sc", "circuit": "bahrain", "ratio": 0.40},
        {"kind": "sc", "circuit": "bahrain", "ratio": 0.36},
        {"kind": "vsc", "circuit": "bahrain", "ratio": 0.50},
    ]
    payload = summarize_events(events)
    assert payload["global"]["sc"] == pytest.approx(0.38)
    heil = payload["heilmeier_table_6"]
    assert "spain" in heil
    catalunya = heilmeier_implied_ratios()["spain"]
    assert catalunya["sc_ratio"] == pytest.approx(7.88 / 19.04)
    # Heilmeier is beside the table, not mixed into the FastF1 median.
    assert payload["global"]["sc"] != pytest.approx(catalunya["sc_ratio"])
    assert payload["meta"]["do_not_average_heilmeier"] is True
    assert payload["meta"]["uncalibrated_default"] == {"sc": 0.35, "vsc": 0.55}
