"""Standings pages are limited to 2024–2026."""

from __future__ import annotations

from backend.models import DriverStandingsResponse
from backend.standings import (
    STANDINGS_2026_UNAVAILABLE,
    STANDINGS_YEAR_LIMIT_MSG,
    StandingsYearBlocked,
    assert_standings_year,
    constructor_standings,
    driver_standings,
)


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


def test_assert_standings_year_blocks_2023():
    try:
        assert_standings_year(2023)
        raise AssertionError("expected StandingsYearBlocked")
    except StandingsYearBlocked as extra:
        assert str(extra) == STANDINGS_YEAR_LIMIT_MSG


def test_assert_allows_2024_2025_2026():
    assert assert_standings_year(2024) == 2024
    assert assert_standings_year(2025) == 2025
    assert assert_standings_year(2026) == 2026


def test_api_standings_2023_is_400():
    from backend.main import app

    client = _client(app)
    for kind in ("drivers", "constructors"):
        r = client.get(f"/api/standings/{kind}/2023")
        assert r.status_code == 400
        assert r.json()["detail"] == STANDINGS_YEAR_LIMIT_MSG


def test_driver_standings_2026_unavailable_message(monkeypatch):
    from backend import standings

    monkeypatch.setattr(standings, "_jolpica", lambda _path: None)
    out = driver_standings(2026)
    assert out.standings == []
    assert out.source == "unavailable"
    assert out.message == STANDINGS_2026_UNAVAILABLE


def test_constructor_standings_2026_unavailable_message(monkeypatch):
    from backend import standings

    monkeypatch.setattr(standings, "_jolpica", lambda _path: None)
    out = constructor_standings(2026)
    assert out.standings == []
    assert out.message == STANDINGS_2026_UNAVAILABLE


def test_driver_standings_2024_empty_has_no_2026_message(monkeypatch):
    from backend import standings

    monkeypatch.setattr(standings, "_jolpica", lambda _path: None)
    out = driver_standings(2024)
    assert out.standings == []
    assert out.message is None


def test_api_standings_2024_ok(monkeypatch):
    from backend import standings
    from backend.main import app
    from backend.models import DriverStanding

    fake = DriverStandingsResponse(
        year=2024,
        standings=[
            DriverStanding(
                position=1,
                driver_code="VER",
                full_name="Max Verstappen",
                team_name="Red Bull",
                points=437,
                wins=9,
                gap_to_leader=0,
            )
        ],
        source="jolpica",
        champion_code="VER",
        leader_code="VER",
    )
    monkeypatch.setattr(standings, "driver_standings", lambda _year: fake)
    client = _client(app)
    r = client.get("/api/standings/drivers/2024")
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2024
    assert body["standings"][0]["driver_code"] == "VER"


def test_api_standings_2026_not_available_payload(monkeypatch):
    from backend import standings
    from backend.main import app

    fake = DriverStandingsResponse(
        year=2026, standings=[], source="unavailable", message=STANDINGS_2026_UNAVAILABLE
    )
    monkeypatch.setattr(standings, "driver_standings", lambda _year: fake)
    client = _client(app)
    r = client.get("/api/standings/drivers/2026")
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == STANDINGS_2026_UNAVAILABLE
    assert body["standings"] == []
