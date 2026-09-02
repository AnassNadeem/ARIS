"""On-demand ghost for any driver who raced — baked file or compute, never silent empty."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aris.ghost_pack import (
    RACE_UNAVAILABLE_MSG,
    DriverDidNotRace,
    GhostDataGap,
    RacePackUnavailable,
    assert_driver_raced,
    clear_ghost_pack_cache,
    get_or_compute_ghost,
)


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


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
                "is_dnf": False,
                "gap_to_leader_s": float(i),
                "track_status": "1",
            }
        )
    return {
        "meta": {
            "year": 2024,
            "round": 3,
            "total_laps": 1,
            "circuit_name": "Albert Park",
            "session_key": 1,
        },
        "drivers": drivers,
        "laps": laps,
    }


def _baked(driver: str = "VER") -> dict:
    return {
        "driver": driver,
        "strategy": {"pit_laps": [20], "compounds": ["HARD"], "label": "baked-label"},
        "ticks": [
            {
                "lap": 1,
                "position": 2,
                "gap_to_leader_s": 1.5,
                "compound": "SOFT",
                "tyre_life": 1,
                "stint": 1,
                "cumulative_delta_s": 0.0,
                "aris_action": "STAY_OUT",
                "aris_confidence": 1.0,
            }
        ],
        "outcome": {
            "aris_action": "STAY_OUT",
            "real_action": "STAY_OUT",
            "verdict": None,
        },
    }


def _computed(driver: str = "HAM") -> dict:
    return {
        "driver": driver,
        "strategy": {"pit_laps": [18], "compounds": ["HARD"], "label": "computed-label"},
        "ticks": [
            {
                "lap": 1,
                "position": 4,
                "gap_to_leader_s": 3.2,
                "compound": "MEDIUM",
                "tyre_life": 1,
                "stint": 1,
                "cumulative_delta_s": -0.4,
                "aris_action": "STAY_OUT",
                "aris_confidence": 1.0,
            }
        ],
        "outcome": {
            "aris_action": "PIT",
            "real_action": "STAY_OUT",
            "verdict": None,
        },
    }


def _pack(tmp: Path, field: dict, ghosts: dict[str, dict] | None = None) -> Path:
    race = tmp / "replay" / "2024" / "3"
    race.mkdir(parents=True)
    (race / "race_field.json").write_text(json.dumps(field), encoding="utf-8")
    for code, payload in (ghosts or {}).items():
        (race / f"ghost_{code}.json").write_text(json.dumps(payload), encoding="utf-8")
    return race


@pytest.fixture
def pack_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ARIS_REPLAY_R2_ROOT", str(tmp_path))
    clear_ghost_pack_cache()
    yield tmp_path
    clear_ghost_pack_cache()


def test_baked_ghost_returned_unchanged(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    baked = _baked("VER")
    race = _pack(pack_env, _field(["VER", "HAM"]), {"VER": baked})
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("compute_ghost must not run for a baked driver")

    monkeypatch.setattr("aris.ghost_pack.compute_ghost", boom)
    out = get_or_compute_ghost(2024, 3, "VER", allow_remote=False)
    assert out["strategy"]["label"] == "baked-label"
    assert out["ticks"][0]["position"] == 2
    assert out["source"] == "baked"
    assert calls["n"] == 0
    on_disk = json.loads((race / "ghost_VER.json").read_text(encoding="utf-8"))
    assert on_disk == baked
    assert "source" not in on_disk


def test_unbaked_racer_gets_computed_and_persisted(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    race = _pack(pack_env, _field(["VER", "HAM"]))
    fake = _computed("HAM")
    calls = {"n": 0}

    def fake_compute(year, round_number, driver, field=None, **_k):
        calls["n"] += 1
        assert int(year) == 2024 and int(round_number) == 3
        assert str(driver).upper() == "HAM"
        assert field is not None
        return dict(fake)

    monkeypatch.setattr("aris.ghost_pack.compute_ghost", fake_compute)
    out = get_or_compute_ghost(2024, 3, "HAM", allow_remote=False)
    assert calls["n"] == 1
    assert out["source"] == "computed"
    assert out["strategy"]["label"] == "computed-label"
    persisted = race / "ghost_HAM.json"
    assert persisted.is_file()
    on_disk = json.loads(persisted.read_text(encoding="utf-8"))
    assert on_disk == fake
    assert "source" not in on_disk

    clear_ghost_pack_cache()
    again = get_or_compute_ghost(2024, 3, "HAM", allow_remote=False)
    assert again["source"] == "baked"
    assert calls["n"] == 1


def test_driver_who_did_not_race_is_rejected(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    _pack(pack_env, _field(["VER", "NOR"]))
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("must not compute a ghost for a non-racer")

    monkeypatch.setattr("aris.ghost_pack.compute_ghost", boom)
    with pytest.raises(DriverDidNotRace, match="BOT did not race this weekend"):
        get_or_compute_ghost(2024, 3, "BOT", allow_remote=False)
    assert calls["n"] == 0
    assert not (pack_env / "replay" / "2024" / "3" / "ghost_BOT.json").exists()


def test_dns_driver_is_rejected_not_empty_ghost(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    _pack(pack_env, _field(["VER", "HUL"], dns=["HUL"]))
    monkeypatch.setattr(
        "aris.ghost_pack.compute_ghost",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no compute")),
    )
    with pytest.raises(DriverDidNotRace, match="HUL did not start"):
        get_or_compute_ghost(2024, 3, "HUL", allow_remote=False)


def test_missing_race_pack_is_unavailable_without_compute(
    pack_env: Path, monkeypatch: pytest.MonkeyPatch
):
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("must not compute when the race pack is missing")

    monkeypatch.setattr("aris.ghost_pack.compute_ghost", boom)
    with pytest.raises(RacePackUnavailable, match=RACE_UNAVAILABLE_MSG):
        get_or_compute_ghost(2025, 22, "VER", allow_remote=False)
    assert calls["n"] == 0


def test_driver_listed_without_laps_is_a_data_gap(pack_env: Path):
    field = _field(["VER"])
    field["drivers"].append(
        {
            "code": "GAS",
            "name": "GAS",
            "team": "Test",
            "colour": "#111",
            "grid_position": 2,
            "is_dns": False,
        }
    )
    _pack(pack_env, field)
    with pytest.raises(GhostDataGap, match="No classified laps for GAS"):
        assert_driver_raced(field, "GAS")
    with pytest.raises(GhostDataGap):
        get_or_compute_ghost(2024, 3, "GAS", allow_remote=False)


def test_ghost_pack_route_registered():
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/aris/ghost-pack" in paths


def test_ghost_pack_http_baked(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    from backend.main import app

    baked = _baked("VER")
    _pack(pack_env, _field(["VER"]), {"VER": baked})
    monkeypatch.setattr(
        "aris.ghost_pack.compute_ghost",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no compute")),
    )
    res = _client(app).get(
        "/api/aris/ghost-pack",
        params={"year": 2024, "round_number": 3, "driver": "VER"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["strategy"]["label"] == "baked-label"
    assert body["source"] == "baked"


def test_ghost_pack_http_unbaked_racer(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    from backend.main import app

    _pack(pack_env, _field(["HAM"]))
    monkeypatch.setattr("aris.ghost_pack.compute_ghost", lambda *_a, **_k: _computed("HAM"))
    res = _client(app).get(
        "/api/aris/ghost-pack",
        params={"year": 2024, "round_number": 3, "driver": "HAM"},
    )
    assert res.status_code == 200
    assert res.json()["source"] == "computed"
    assert res.json()["driver"] == "HAM"


def test_ghost_pack_http_non_racer(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    from backend.main import app

    _pack(pack_env, _field(["VER"]))
    monkeypatch.setattr(
        "aris.ghost_pack.compute_ghost",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no compute")),
    )
    res = _client(app).get(
        "/api/aris/ghost-pack",
        params={"year": 2024, "round_number": 3, "driver": "BOT"},
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "driver_did_not_race"
    assert "BOT" in detail["message"]


def test_ghost_pack_http_missing_race(pack_env: Path, monkeypatch: pytest.MonkeyPatch):
    from backend.main import app

    monkeypatch.setattr(
        "aris.ghost_pack.compute_ghost",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no compute")),
    )
    res = _client(app).get(
        "/api/aris/ghost-pack", params={"year": 2025, "round_number": 22, "driver": "VER"}
    )
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["code"] == "race_unavailable"
    assert detail["message"] == RACE_UNAVAILABLE_MSG
