"""TrackConfig compound_slopes override wiring (Phase E1.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from aris.physics.bicycle import Car, Corner, StintState, Track, predict_lap_time
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE, tire_pace_loss
from aris.tracks import clear_track_config_cache, load_track_config


def test_netherlands_yaml_can_carry_compound_slopes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tracks_dir = tmp_path / "tracks"
    tracks_dir.mkdir()
    doc = {
        "name": "Netherlands",
        "country": "Netherlands",
        "total_laps": 72,
        "pit_loss_s": 16.4,
        "lap_length_m": 4200.0,
        "corners": [{"radius_m": 50.0, "arc_length_m": 60.0}],
        "round_aliases": ["netherlands", "zandvoort"],
        "compound_slopes": {"SOFT": 0.12, "MEDIUM": 0.06, "HARD": 0.02},
    }
    (tracks_dir / "netherlands.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.setattr("aris.tracks._TRACKS_DIR", tracks_dir)
    clear_track_config_cache()
    cfg = load_track_config("Zandvoort")
    assert cfg.compound_slopes is not None
    assert cfg.compound_slopes["SOFT"] == pytest.approx(0.12)
    track = cfg.load_physics()
    assert track.compound_slopes is not None
    assert track.compound_slopes["SOFT"] == pytest.approx(0.12)

    state = StintState(
        car=Car(),
        track=track,
        compound="SOFT",
        lap_in_stint=5,
        fuel_kg=0.0,
    )
    pred = predict_lap_time(state)
    # Same physics corners, but tyre term uses override slope.
    base_track = Track(
        corners=track.corners,
        straight_length_m=track.straight_length_m,
        name=track.name,
        pit_loss_s=track.pit_loss_s,
        compound_slopes=None,
    )
    base = predict_lap_time(StintState(car=Car(), track=base_track, compound="SOFT", lap_in_stint=5))
    expected_delta = tire_pace_loss("SOFT", 5, slopes=cfg.compound_slopes) - tire_pace_loss("SOFT", 5)
    assert pred - base == pytest.approx(expected_delta)
    clear_track_config_cache()


def test_other_tracks_keep_global_defaults():
    clear_track_config_cache()
    cfg = load_track_config("Bahrain")
    # E2.3 may persist explicit global compound_slopes on YAML after a
    # fallback; either None or the DEFAULT_COMPOUND_SLOPE dry triple is fine.
    if cfg.compound_slopes is not None:
        for k in ("SOFT", "MEDIUM", "HARD"):
            assert cfg.compound_slopes[k] == pytest.approx(DEFAULT_COMPOUND_SLOPE[k])
    track = cfg.load_physics()
    loss = tire_pace_loss("MEDIUM", 4, slopes=track.compound_slopes)
    assert loss == pytest.approx(DEFAULT_COMPOUND_SLOPE["MEDIUM"] * 3)


def test_n_corners_netherlands_from_yaml():
    from aris.tracks import n_corners_for_event

    n = n_corners_for_event("Netherlands")
    assert n is not None and n >= 10


def test_n_corners_bahrain_from_physics_profile():
    from aris.tracks import n_corners_for_event

    assert n_corners_for_event("Bahrain") == 15


def test_n_corners_spanish_grand_prix_alias():
    from aris.tracks import n_corners_for_event

    assert n_corners_for_event("Spanish Grand Prix") == n_corners_for_event("Spain")
    assert n_corners_for_event("Spain") == 14


def test_n_corners_unmatched_is_none():
    from aris.tracks import n_corners_for_event

    assert n_corners_for_event("Atlantis Grand Prix") is None


def test_n_corners_mugello_empty_list_is_none():
    from aris.tracks import n_corners_for_event

    # YAML has corners: [] — not a fabricated Bahrain fallback.
    assert n_corners_for_event("Tuscany") is None
    assert n_corners_for_event("Mugello") is None
