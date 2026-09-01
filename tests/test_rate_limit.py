"""Per-IP compute quotas and ghost-recompute error/timeout bodies."""

from __future__ import annotations

import asyncio

import pytest

from backend.rate_limit import COMPUTE_LIMITS, reset_for_tests


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_quota():
    reset_for_tests()
    yield
    reset_for_tests()


def test_ghost_recompute_missing_driver_is_422():
    from backend.main import app

    client = _client(app)
    response = client.post(
        "/api/aris/ghost-recompute",
        json={
            "year": 2024,
            "round": 15,
            "driver": "   ",
            "current_lap": 10,
            "pit_laps": [20],
            "compounds": ["HARD"],
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    detail = body["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "ghost_uncomputable"


def test_ghost_recompute_cold_pack_is_503_with_body():
    from backend.main import app

    client = _client(app)
    response = client.post(
        "/api/aris/ghost-recompute",
        json={
            "year": 1999,
            "round": 1,
            "driver": "VER",
            "current_lap": 10,
            "pit_laps": [20],
            "compounds": ["HARD"],
        },
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("code") == "replay_pack_not_warm"
    assert "error" in detail


def test_ghost_recompute_timeout_is_504(monkeypatch: pytest.MonkeyPatch):
    from backend import main as main_mod

    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr(main_mod, "GHOST_RECOMPUTE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(main_mod, "run_light", _hang)
    client = _client(main_mod.app)
    response = client.post(
        "/api/aris/ghost-recompute",
        json={
            "year": 2024,
            "round": 15,
            "driver": "VER",
            "current_lap": 10,
            "pit_laps": [20],
            "compounds": ["HARD"],
        },
    )
    assert response.status_code == 504
    detail = response.json()["detail"]
    assert detail.get("code") == "ghost_recompute_timeout"
    assert "error" in detail


def test_ghost_recompute_rate_limit_is_429():
    from backend.main import app

    client = _client(app)
    payload = {
        "year": 1999,
        "round": 1,
        "driver": "VER",
        "current_lap": 10,
        "pit_laps": [20],
        "compounds": ["HARD"],
    }
    max_n, _window = COMPUTE_LIMITS["/api/aris/ghost-recompute"]
    last = None
    for _ in range(max_n + 1):
        last = client.post("/api/aris/ghost-recompute", json=payload)
    assert last is not None
    assert last.status_code == 429
    detail = last.json()["detail"]
    assert detail.get("code") == "rate_limited"


def test_cached_calendar_is_not_rate_limited():
    from backend.main import app

    client = _client(app)
    for _ in range(25):
        response = client.get("/api/health")
        assert response.status_code != 429
