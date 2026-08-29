"""Replay FastF1 window: only 2024–2026 may load session data."""

from __future__ import annotations

import asyncio
import logging

import pytest

from backend.calendar import (
    ALLOWED_REPLAY_YEARS,
    REPLAY_YEAR_LIMIT_MSG,
    ReplayYearBlocked,
    assert_replay_year,
    replay_year_allowed,
)


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


def test_allowed_replay_years_are_the_last_three_seasons():
    assert ALLOWED_REPLAY_YEARS == frozenset({2024, 2025, 2026})
    assert replay_year_allowed(2025) is True
    assert replay_year_allowed(2023) is False
    assert replay_year_allowed(2018) is False


def test_assert_replay_year_logs_allowed_and_blocked(caplog):
    caplog.set_level(logging.INFO)
    assert assert_replay_year(2025) == 2025
    assert any("Replay request for year 2025 — allowed" in r.message for r in caplog.records)
    caplog.clear()
    with pytest.raises(ReplayYearBlocked, match="2024, 2025, and 2026"):
        assert_replay_year(2023)
    assert any(
        "Replay request for year 2023 — blocked (not in 2024–2026)" in r.message for r in caplog.records
    )


def test_load_session_blocks_2023_before_fastf1(monkeypatch, caplog):
    from backend import sessions

    caplog.set_level(logging.INFO)

    def boom(*_a, **_k):
        raise AssertionError("FastF1 must not be called for 2023")

    monkeypatch.setattr(sessions, "_get_fastf1_session", boom)
    monkeypatch.setattr(sessions, "_blocked_open_session", boom)
    with pytest.raises(ReplayYearBlocked, match="Replay not allowed for this year"):
        sessions.load_session(2023, 1, "R")
    assert any("blocked (not in 2024–2026)" in r.message for r in caplog.records)


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_load_session_allows_window_years_past_the_guard(monkeypatch, year):
    from backend import sessions

    sentinel = object()
    monkeypatch.setattr(sessions, "_blocked_open_session", lambda *_a, **_k: False)
    monkeypatch.setattr(sessions, "_SESSION_CACHE", {})
    monkeypatch.setattr(sessions, "_SESSION_FLAGS", {})

    class FakeSess:
        def load(self, **_k):
            return None

    monkeypatch.setattr(sessions, "_get_fastf1_session", lambda *_a, **_k: FakeSess())
    out = sessions.load_session(year, 1, "R", telemetry=False, weather=False, messages=False)
    assert out is not sentinel
    assert isinstance(out, FakeSess)


def test_get_calendar_for_replay_skips_fastf1(monkeypatch):
    from backend import calendar as cal

    monkeypatch.setattr(cal, "_schedule_from_fastf1", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("FastF1")))
    with pytest.raises(ReplayYearBlocked):
        cal.get_calendar(2023, for_replay=True)


def test_replay_init_http_blocks_2023(monkeypatch, caplog):
    from backend.main import app
    from backend import live as live_mod

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        live_mod,
        "_kick_pack_job",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no FastF1 pack job")),
    )
    monkeypatch.setattr(
        live_mod,
        "init_replay",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("init_replay must not run")),
    )
    client = _client(app)
    res = client.post("/api/replay/init", json={"year": 2023, "round_number": 1, "session_type": "R"})
    assert res.status_code == 400
    assert REPLAY_YEAR_LIMIT_MSG in res.json()["detail"]
    assert any("blocked (not in 2024–2026)" in r.message for r in caplog.records)


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_replay_init_http_allows_window_years(monkeypatch, year):
    from backend.main import app
    from backend import live as live_mod

    async def fake_init(y, round_number, session_type):
        return {
            "session_key": live_mod.synthetic_session_key(y, round_number, session_type),
            "year": y,
            "round_number": round_number,
            "session_type": session_type,
            "stage": "metadata",
            "session_status": "COMPLETED",
            "source": "fastf1",
            "circuit": "Test",
            "total_laps": 50,
            "drivers": [],
            "date_start": None,
            "date_end": None,
            "flags": {},
            "progress": 0.0,
        }

    monkeypatch.setattr(live_mod, "init_replay", fake_init)
    client = _client(app)
    res = client.post("/api/replay/init", json={"year": year, "round_number": 1, "session_type": "R"})
    assert res.status_code == 200, res.text
    assert res.json()["year"] == year


def test_prewarm_http_blocks_2023():
    from backend.main import app

    client = _client(app)
    res = client.post("/api/prewarm", json={"year": 2023, "round_number": 1, "session_type": "R"})
    assert res.status_code == 400
    assert "2024" in res.json()["detail"]


def test_calendar_replay_query_blocks_2023(monkeypatch):
    from backend.main import app
    from backend import calendar as cal

    monkeypatch.setattr(
        cal,
        "get_calendar",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("FastF1 calendar must not run")),
    )
    client = _client(app)
    res = client.get("/api/calendar/2023?replay=1")
    assert res.status_code == 400
    assert REPLAY_YEAR_LIMIT_MSG in res.json()["detail"]


def test_init_replay_direct_blocks_before_calendar(monkeypatch):
    from backend import live as live_mod
    from backend import calendar as cal

    monkeypatch.setattr(
        cal,
        "get_round",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("calendar/FastF1 must not run")),
    )
    monkeypatch.setattr(
        live_mod,
        "_kick_pack_job",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no pack job")),
    )
    with pytest.raises(ReplayYearBlocked):
        asyncio.run(live_mod.init_replay(2023, 1, "R"))
