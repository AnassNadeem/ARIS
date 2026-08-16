"""Live-write gate vs true-compound overlay — independent controls (Phase G.6)."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from aris.physics.compounds import TRUE_COMPOUND_SLOPES_ENV, parse_true_compound_mode

_ROOT = Path(__file__).resolve().parents[1]
_FIT_PATH = _ROOT / "scripts" / "fit_zandvoort_tire_slopes.py"


def _load_fit():
    spec = importlib.util.spec_from_file_location("fit_zandvoort_tire_slopes", _FIT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fit():
    return _load_fit()


def test_event_window_is_actual_zandvoort_weekend(fit):
    assert fit._EVENT_WINDOW == (date(2026, 8, 21), date(2026, 8, 23))


@pytest.mark.parametrize(
    "day, inside",
    [
        (date(2026, 8, 20), False),
        (date(2026, 8, 21), True),
        (date(2026, 8, 22), True),
        (date(2026, 8, 23), True),
        (date(2026, 8, 24), False),
        (date(2026, 8, 15), False),  # this rehearsal day, 6 days out
    ],
)
def test_in_event_window_actual_dates(fit, day, inside):
    assert fit._in_event_window(day) is inside


def test_fit_script_source_does_not_read_overlay_env(fit):
    src = _FIT_PATH.read_text(encoding="utf-8")
    assert "ARIS_TRUE_COMPOUND_SLOPES" not in src
    assert "parse_true_compound_mode" not in src
    assert "true_compound" not in src.lower()


def test_overlay_env_does_not_change_event_window(fit, monkeypatch):
    monkeypatch.setenv(TRUE_COMPOUND_SLOPES_ENV, "pooled")
    assert parse_true_compound_mode() == "pooled"
    assert fit._in_event_window(date(2026, 8, 22)) is True
    assert fit._in_event_window(date(2026, 8, 15)) is False
    monkeypatch.delenv(TRUE_COMPOUND_SLOPES_ENV, raising=False)
    assert parse_true_compound_mode() == "off"
    assert fit._in_event_window(date(2026, 8, 22)) is True


def _fake_metrics() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Compound": ["SOFT", "MEDIUM", "HARD"],
            "DegSlope": [0.08, 0.05, 0.03],
            "NumLaps": [10, 10, 10],
            "SessionKey": ["2025-R"] * 3,
            "FuelCorrected": [True, True, True],
            "TrackEvolutionCorrected": [False, False, False],
        }
    )


def test_write_refused_inside_window_without_allow(fit, monkeypatch, tmp_path):
    monkeypatch.setattr(fit, "collect_long_run_metrics", lambda **kwargs: _fake_metrics())
    monkeypatch.setattr(fit, "_in_event_window", lambda today=None: True)
    monkeypatch.setattr(fit, "_ROOT", tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["fit_zandvoort_tire_slopes.py", "--write"],
    )
    with pytest.raises(SystemExit) as exc:
        fit.main()
    assert exc.value.code == 2


def test_write_allowed_inside_window_with_allow(fit, monkeypatch, tmp_path):
    yaml_path = tmp_path / "netherlands.yaml"
    yaml_path.write_text("name: Netherlands\ncompound_slopes: {}\n", encoding="utf-8")
    monkeypatch.setattr(fit, "collect_long_run_metrics", lambda **kwargs: _fake_metrics())
    monkeypatch.setattr(fit, "_in_event_window", lambda today=None: True)
    monkeypatch.setattr(fit, "_YAML", yaml_path)
    monkeypatch.setattr(fit, "_ROOT", tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["fit_zandvoort_tire_slopes.py", "--write", "--allow-live-write", "--force-defaults"],
    )
    fit.main()
    text = yaml_path.read_text(encoding="utf-8")
    assert "compound_slopes" in text
    assert "SOFT" in text


def test_log_only_inside_window_does_not_write(fit, monkeypatch, tmp_path):
    yaml_path = tmp_path / "netherlands.yaml"
    original = "name: Netherlands\ncompound_slopes:\n  SOFT: 0.08\n"
    yaml_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(fit, "collect_long_run_metrics", lambda **kwargs: _fake_metrics())
    monkeypatch.setattr(fit, "_in_event_window", lambda today=None: True)
    monkeypatch.setattr(fit, "_YAML", yaml_path)
    monkeypatch.setattr(fit, "_ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["fit_zandvoort_tire_slopes.py"])
    fit.main()
    assert yaml_path.read_text(encoding="utf-8") == original
