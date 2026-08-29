"""T10-A — SC/VSC risk probabilities stay valid and degrade safely."""

from __future__ import annotations

from pathlib import Path

import pytest

from aris.risk.sc_risk_model import (
    BASE_RATE_10,
    BASE_RATE_5,
    circuit_key,
    default_feature_row,
    load_sc_risk_models,
    predict_sc_risk,
    reset_sc_risk_cache,
)


def _features(circuit: str, **overrides) -> dict:
    row = default_feature_row(
        circuit=circuit,
        lap_number=25,
        total_laps=50,
        rain_flag=False,
        track_temp_c=30.0,
    )
    row.update(overrides)
    return row


def test_probabilities_in_valid_range():
    p5, p10 = predict_sc_risk(_features("bahrain"))
    assert 0.0 <= p5 <= 1.0
    assert 0.0 <= p10 <= 1.0


def test_5lap_leq_10lap():
    for circuit in ("azerbaijan", "italy", "bahrain", "monaco"):
        p5, p10 = predict_sc_risk(_features(circuit, lap_number=20, race_frac=0.4))
        assert p5 <= p10


def test_baku_higher_than_monza():
    models = load_sc_risk_models()
    if models is None:
        pytest.skip("SC risk models not trained")
    baku = _features("azerbaijan")
    monza = _features("italy")
    # Same weather / lap; historical rate still differs by circuit.
    p_baku, _ = predict_sc_risk(baku, models=models)
    p_monza, _ = predict_sc_risk(monza, models=models)
    assert circuit_key("baku") == "azerbaijan"
    assert circuit_key("monza") == "italy"
    assert p_baku > p_monza


def test_default_when_models_not_loaded(tmp_path: Path, monkeypatch):
    reset_sc_risk_cache()
    missing = tmp_path / "nope.pkl"
    monkeypatch.setattr(
        "aris.risk.sc_risk_model.MODEL_5_PATH", missing
    )
    monkeypatch.setattr(
        "aris.risk.sc_risk_model.MODEL_10_PATH", missing
    )
    reset_sc_risk_cache()
    assert load_sc_risk_models() is None
    p5, p10 = predict_sc_risk(_features("bahrain"))
    assert p5 == BASE_RATE_5
    assert p10 == BASE_RATE_10
    reset_sc_risk_cache()
