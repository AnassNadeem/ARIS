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


def _grid(*codes: str):
    from backend.models import Driver

    return [
        Driver(driver_code=code, full_name=code, team_name="Team", team_colour="#111111")
        for code in codes
    ]


def test_apply_lineup_replaces_hadjar_from_zandvoort():
    from backend.standings import _apply_weekend_lineup

    rows = _grid("VER", "HAD", "NOR")
    out = [d.driver_code for d in _apply_weekend_lineup(rows, 2026, 17)]
    assert "HAD" not in out
    assert "TSU" in out
    assert "VER" in out
    hungary = [d.driver_code for d in _apply_weekend_lineup(rows, 2026, 14)]
    assert "HAD" in hungary
    assert "TSU" not in hungary


def test_apply_lineup_keeps_session_rookie_without_forcing_tsunoda():
    from backend.standings import _apply_weekend_lineup

    # FP1 already published without HAD — do not invent a 23rd car.
    rows = _grid("VER", "BEA", "NOR")
    out = [d.driver_code for d in _apply_weekend_lineup(rows, 2026, 17)]
    assert "HAD" not in out
    assert "TSU" not in out
    assert "BEA" in out


def test_get_drivers_checks_each_session_entry_list(monkeypatch):
    from backend import standings

    by_session = {
        "FP1": _grid("VER", "TSU", "NOR", "PIA", "LEC", "HAM", "RUS", "ANT", "ALO", "STR"),
        "FP2": _grid("VER", "HAD", "NOR", "PIA", "LEC", "HAM", "RUS", "ANT", "ALO", "STR"),
        "Q": _grid("VER", "TSU", "NOR", "PIA", "LEC", "HAM", "RUS", "ANT", "ALO", "STR"),
        "R": _grid("VER", "HAD", "NOR", "PIA", "LEC", "HAM", "RUS", "ANT", "ALO", "STR"),
    }

    monkeypatch.setattr(
        standings,
        "_session_entry_drivers",
        lambda _year, _round=None, session_type=None: by_session[str(session_type or "R")],
    )
    monkeypatch.setattr(standings, "_drivers_from_fastf1", lambda _year: [])

    for stype, expect_tsu, expect_had in (
        ("FP1", True, False),
        ("FP2", True, False),
        ("Q", True, False),
        ("R", True, False),
    ):
        codes = [d.driver_code for d in standings.get_drivers(2026, 17, stype).drivers]
        assert ("TSU" in codes) is expect_tsu, stype
        assert ("HAD" in codes) is expect_had, stype


def test_session_entry_uses_named_openf1_session(monkeypatch):
    from backend import standings
    from backend.models import Driver

    def fake_key(_year, _round, session_type):
        return {"FP1": 11, "FP2": 22}.get(session_type)

    def fake_from_key(key):
        extra = "BEA" if key == 11 else "TSU"
        codes = ["VER", extra, "NOR", "PIA", "LEC", "HAM", "RUS", "ANT", "ALO", "STR"]
        return [
            Driver(driver_code=c, full_name=c, team_name="Team", team_colour="#111")
            for c in codes
        ]

    monkeypatch.setattr(standings, "_openf1_session_key_for", fake_key)
    monkeypatch.setattr(standings, "_meeting_sessions", lambda *_a, **_k: [])
    monkeypatch.setattr(standings, "_openf1_session_key", lambda _year: 22)
    monkeypatch.setattr(standings, "_drivers_from_openf1_key", fake_from_key)

    fp1 = [d.driver_code for d in standings._session_entry_drivers(2026, 17, "FP1")]
    fp2 = [d.driver_code for d in standings._session_entry_drivers(2026, 17, "FP2")]
    assert "BEA" in fp1
    assert "TSU" not in fp1
    assert "TSU" in fp2
    assert "BEA" not in fp2
