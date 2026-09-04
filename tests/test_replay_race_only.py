"""Replay/ARIS is Race-only: session lists, pack init, and prebuild."""

from __future__ import annotations

import pytest

from backend.calendar import (
    REPLAY_SESSION_ONLY_MSG,
    ReplaySessionBlocked,
    assert_replay_session_type,
    get_round_sessions,
)


def _client(app):
    from fastapi.testclient import TestClient

    try:
        return TestClient(app, lifespan="off")
    except TypeError:
        return TestClient(app)


def test_assert_replay_session_type_allows_weekend_sessions():
    assert assert_replay_session_type("R") == "R"
    assert assert_replay_session_type("r") == "R"
    assert assert_replay_session_type("FP1") == "FP1"
    assert assert_replay_session_type("FP2") == "FP2"
    assert assert_replay_session_type("Q") == "Q"
    with pytest.raises(ReplaySessionBlocked, match="Only Race sessions"):
        assert_replay_session_type("XX")


def test_get_round_sessions_replay_flag_returns_race_only():
    weekend = get_round_sessions(2026, 15, replay=True)
    types = [s.session_type for s in weekend.sessions]
    assert types == ["R"]
    assert "FP1" not in types
    assert "Q" not in types
    assert "S" not in types


def test_replay_calendar_hides_cancelled_2026():
    from backend.main import app

    client = _client(app)
    res = client.get("/api/calendar/2026?replay=1")
    assert res.status_code == 200
    rounds = res.json()["rounds"]
    assert all(r["status"] not in {"CANCELLED", "UPCOMING"} for r in rounds)
    names = " ".join((r.get("name") or "") + " " + (r.get("circuit_name") or "") for r in rounds).lower()
    assert "bahrain" not in names
    assert "saudi" not in names


def test_get_round_sessions_default_still_lists_weekend():
    weekend = get_round_sessions(2026, 15, replay=False)
    types = {s.session_type for s in weekend.sessions}
    assert "R" in types
    assert len(types) > 1


def test_replay_init_http_rejects_unknown_session(monkeypatch):
    from backend.main import app
    from backend import live as live_mod

    monkeypatch.setattr(
        live_mod,
        "init_replay",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("init_replay must not run")),
    )
    client = _client(app)
    res = client.post("/api/replay/init", json={"year": 2025, "round_number": 15, "session_type": "XX"})
    assert res.status_code == 400
    assert REPLAY_SESSION_ONLY_MSG in str(res.json()["detail"])


def test_replay_sessions_http_race_only():
    from backend.main import app

    client = _client(app)
    res = client.get("/api/calendar/2026/15/sessions?replay=1")
    assert res.status_code == 200
    types = [s["session_type"] for s in res.json()["sessions"]]
    assert types == ["R"]
    assert not any(t in {"FP1", "FP2", "FP3", "Q", "S", "SQ"} for t in types)


def test_init_replay_direct_rejects_unknown_session():
    import asyncio
    from backend import live as live_mod

    with pytest.raises(ReplaySessionBlocked, match="Only Race sessions"):
        asyncio.run(live_mod.init_replay(2025, 15, "XX"))


def test_prebuild_jobs_are_race_only(monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path
    from types import SimpleNamespace

    script = Path(__file__).resolve().parents[1] / "scripts" / "prebuild_replay_packs.py"
    spec = importlib.util.spec_from_file_location("prebuild_replay_packs", script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    monkeypatch.setattr(
        "backend.calendar.get_calendar",
        lambda year, *a, **k: SimpleNamespace(
            rounds=[SimpleNamespace(round_number=1, name="Bahrain", circuit_name="BIC", status="COMPLETED")]
        ),
    )
    monkeypatch.setattr(
        "backend.calendar.get_round_sessions",
        lambda year, rnd, as_of=None, replay=False: SimpleNamespace(
            sessions=[
                SimpleNamespace(session_type="FP1", status="COMPLETED"),
                SimpleNamespace(session_type="Q", status="COMPLETED"),
                SimpleNamespace(session_type="R", status="COMPLETED"),
            ]
        ),
    )
    jobs = mod.iter_prebuild_jobs((2025,), session_type="Q")
    assert jobs
    assert all(j.session_type == "R" for j in jobs)
